use crate::model::Settings;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::fs::{self, File, Metadata, Permissions};
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::time::SystemTime;

#[cfg(unix)]
use std::os::unix::fs::MetadataExt;
#[cfg(windows)]
use std::os::windows::fs::MetadataExt;

fn linked(metadata: &Metadata) -> bool {
    #[cfg(windows)]
    if metadata.file_attributes() & 0x400 != 0 {
        return true;
    }
    metadata.file_type().is_symlink()
}

fn walk(root: &Path, candidates: &mut Vec<PathBuf>) -> io::Result<()> {
    for entry in fs::read_dir(root)? {
        let path = entry?.path();
        let metadata = fs::symlink_metadata(&path)?;
        if linked(&metadata) {
            continue;
        }
        if metadata.is_dir() {
            walk(&path, candidates)?;
        } else if metadata.is_file()
            && path
                .file_name()
                .is_some_and(|name| name.to_string_lossy().ends_with(".py"))
        {
            candidates.push(path);
        }
    }
    Ok(())
}

fn absolute_key(path: &Path) -> io::Result<PathBuf> {
    let absolute = std::path::absolute(path)?;
    #[cfg(windows)]
    let absolute = PathBuf::from(absolute.to_string_lossy().to_lowercase());
    Ok(absolute)
}

pub fn discover(settings: &Settings) -> Result<Vec<PathBuf>, String> {
    if settings.paths.is_empty() {
        return Err("Please specify at least one path to inspect".into());
    }
    let ignored_folders = settings
        .ignore_folders
        .iter()
        .map(|path| absolute_key(path))
        .collect::<io::Result<Vec<_>>>()
        .map_err(|error| error.to_string())?;
    let mut paths = HashMap::new();
    for path in &settings.paths {
        let metadata = fs::metadata(path)
            .map_err(|error| format!("Invalid path: {}: {error}", path.display()))?;
        let mut candidates = Vec::new();
        if metadata.is_dir() {
            if linked(&fs::symlink_metadata(path).map_err(|error| error.to_string())?) {
                return Err(format!(
                    "Refusing symlink or reparse-point directory: {}",
                    path.display()
                ));
            }
            walk(path, &mut candidates).map_err(|error| error.to_string())?;
        } else if metadata.is_file() {
            candidates.push(path.clone());
        } else {
            return Err(format!("Invalid path: {}", path.display()));
        }
        for candidate in candidates {
            let key = absolute_key(&candidate).map_err(|error| error.to_string())?;
            if candidate.file_name().is_some_and(|name| {
                settings
                    .ignore_files
                    .iter()
                    .any(|ignored| name == ignored.as_str())
            }) || ignored_folders.iter().any(|folder| key.starts_with(folder))
            {
                continue;
            }
            paths.entry(key).or_insert(candidate);
        }
    }
    let mut paths: Vec<_> = paths.into_values().collect();
    paths.sort_by_cached_key(|path| path.to_string_lossy().replace('\\', "/"));
    Ok(paths)
}

#[derive(Debug, PartialEq, Eq)]
struct Stamp {
    size: u64,
    modified: SystemTime,
    readonly: bool,
    #[cfg(unix)]
    unix: (u64, u64, u32, u64, i64, i64),
    #[cfg(windows)]
    windows: (u32, u64),
}

fn stamp(metadata: &Metadata) -> io::Result<Stamp> {
    Ok(Stamp {
        size: metadata.len(),
        modified: metadata.modified()?,
        readonly: metadata.permissions().readonly(),
        #[cfg(unix)]
        unix: (
            metadata.dev(),
            metadata.ino(),
            metadata.mode(),
            metadata.nlink(),
            metadata.ctime(),
            metadata.ctime_nsec(),
        ),
        #[cfg(windows)]
        windows: (metadata.file_attributes(), metadata.creation_time()),
    })
}

#[cfg(unix)]
fn link_count(file: &File) -> io::Result<u64> {
    Ok(file.metadata()?.nlink())
}

#[cfg(windows)]
fn link_count(file: &File) -> io::Result<u64> {
    Ok(winapi_util::file::information(file)?.number_of_links())
}

#[cfg(not(any(unix, windows)))]
fn link_count(_file: &File) -> io::Result<u64> {
    Ok(0)
}

#[cfg(windows)]
type FileId = (u64, [u8; 16]);

#[cfg(windows)]
fn file_id(file: &File) -> io::Result<FileId> {
    use std::os::windows::io::AsRawHandle;
    use windows_sys::Win32::Storage::FileSystem::{
        FILE_ID_INFO, FileIdInfo, GetFileInformationByHandleEx,
    };

    let mut info = FILE_ID_INFO::default();
    // The live file handle and writable buffer remain valid for this call.
    let success = unsafe {
        GetFileInformationByHandleEx(
            file.as_raw_handle(),
            FileIdInfo,
            (&mut info as *mut FILE_ID_INFO).cast(),
            std::mem::size_of::<FILE_ID_INFO>() as u32,
        )
    };
    if success == 0 {
        return Err(io::Error::last_os_error());
    }
    Ok((info.VolumeSerialNumber, info.FileId.Identifier))
}

#[derive(Debug)]
struct Identity {
    stamp: Stamp,
    digest: [u8; 32],
    links: u64,
    permissions: Permissions,
    #[cfg(windows)]
    file_id: FileId,
    // Keep Windows IDs valid until the original snapshot is released.
    #[cfg(windows)]
    _handle: File,
}

#[derive(Debug)]
pub struct Snapshot {
    pub bytes: Vec<u8>,
    pub unsafe_reason: Option<String>,
    identity: Option<Identity>,
}

fn unsafe_path(
    path: &Path,
    metadata: &Metadata,
    links: u64,
    project_root: &Path,
) -> io::Result<Option<String>> {
    if linked(metadata) {
        return Ok(Some("repair target is a symlink or reparse point".into()));
    }
    if !metadata.is_file() {
        return Ok(Some("repair target is not a regular file".into()));
    }
    if links == 0 {
        return Ok(Some("repair target has no supported file identity".into()));
    }
    if links != 1 {
        return Ok(Some(format!("repair target has {links} hard links")));
    }
    let absolute = std::path::absolute(path)?;
    let root = std::path::absolute(project_root)?;
    for parent in absolute.ancestors().skip(1) {
        if Some(parent) == root.parent() || parent.parent().is_none() {
            break;
        }
        if linked(&fs::symlink_metadata(parent)?) {
            return Ok(Some(
                "repair target traverses a symlink or reparse-point parent".into(),
            ));
        }
    }
    Ok(None)
}

pub fn read(path: &Path, project_root: &Path) -> io::Result<Snapshot> {
    let before = fs::symlink_metadata(path)?;
    let mut file = File::open(path)?;
    let opened = file.metadata()?;
    #[cfg(windows)]
    let original_id = file_id(&file)?;
    let links = link_count(&file)?;
    let mut bytes = Vec::new();
    file.read_to_end(&mut bytes)?;
    let read_metadata = file.metadata()?;
    let after = fs::symlink_metadata(path)?;
    let mut unsafe_reason = unsafe_path(path, &after, links, project_root)?;
    let current_stamp = stamp(&after)?;
    if unsafe_reason.is_none()
        && (stamp(&before)? != current_stamp
            || stamp(&opened)? != current_stamp
            || stamp(&read_metadata)? != current_stamp
            || link_count(&file)? != links)
    {
        unsafe_reason = Some("repair target changed while it was read".into());
    }
    #[cfg(windows)]
    if unsafe_reason.is_none() && original_id != file_id(&File::open(path)?)? {
        unsafe_reason = Some("repair target changed while it was read".into());
    }
    let identity = unsafe_reason.is_none().then(|| Identity {
        stamp: current_stamp,
        digest: Sha256::digest(&bytes).into(),
        links,
        permissions: after.permissions(),
        #[cfg(windows)]
        file_id: original_id,
        #[cfg(windows)]
        _handle: file,
    });
    Ok(Snapshot {
        bytes,
        unsafe_reason,
        identity,
    })
}

#[derive(Debug)]
pub enum RepairError {
    Unsafe(String),
    Io(io::Error),
}

impl From<io::Error> for RepairError {
    fn from(error: io::Error) -> Self {
        Self::Io(error)
    }
}

fn matches(path: &Path, identity: &Identity, project_root: &Path) -> io::Result<bool> {
    let current = read(path, project_root)?;
    Ok(current.identity.is_some_and(|current| {
        #[cfg(windows)]
        if current.file_id != identity.file_id {
            return false;
        }
        current.stamp == identity.stamp
            && current.digest == identity.digest
            && current.links == identity.links
    }))
}

pub fn replace(
    path: &Path,
    original: &Snapshot,
    repaired: &[u8],
    project_root: &Path,
) -> Result<(), RepairError> {
    let identity = original.identity.as_ref().ok_or_else(|| {
        RepairError::Unsafe(
            original
                .unsafe_reason
                .clone()
                .unwrap_or_else(|| "repair target is unsafe".into()),
        )
    })?;
    if !matches(path, identity, project_root)? {
        return Err(RepairError::Unsafe(
            "repair target changed before writing".into(),
        ));
    }
    if original.bytes == repaired {
        return Ok(());
    }
    let parent = path
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    let mut temporary = tempfile::Builder::new()
        .prefix(".lmh-")
        .tempfile_in(parent)?;
    temporary.write_all(repaired)?;
    temporary
        .as_file()
        .set_permissions(identity.permissions.clone())?;
    temporary.as_file().sync_all()?;
    if !matches(path, identity, project_root)? {
        return Err(RepairError::Unsafe(
            "repair target changed before replacement".into(),
        ));
    }
    temporary
        .persist(path)
        .map_err(|error| RepairError::Io(error.error))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn settings(root: &Path) -> Settings {
        Settings {
            owner: "Owner".into(),
            year: 2020,
            license: None,
            license_notice: None,
            license_path: root.join("LICENSE"),
            paths: vec![root.to_path_buf()],
            ignore_files: vec!["ignored.py".into()],
            ignore_folders: vec![root.join("skip")],
            project_root: root.to_path_buf(),
            config_path: None,
        }
    }

    #[test]
    fn discovery_is_sorted_deduplicated_and_honors_ignores() {
        let root = tempfile::tempdir().unwrap();
        fs::create_dir(root.path().join("skip")).unwrap();
        for name in [
            "z.py",
            "a.py",
            ".py",
            "other.txt",
            "ignored.py",
            "skip/a.py",
        ] {
            fs::write(root.path().join(name), b"content").unwrap();
        }
        let mut settings = settings(root.path());
        settings.paths.push(root.path().join("./a.py"));
        assert_eq!(
            discover(&settings).unwrap(),
            vec![
                root.path().join(".py"),
                root.path().join("a.py"),
                root.path().join("z.py")
            ]
        );
        settings.ignore_folders.push(root.path().to_path_buf());
        assert!(discover(&settings).unwrap().is_empty());
    }

    #[test]
    fn read_and_noop_do_not_write_and_repair_preserves_bytes_and_mode() {
        let root = tempfile::tempdir().unwrap();
        let path = root.path().join("source.py");
        let original = b"\xef\xbb\xbf# coding: utf-8\r\n# Copyright (C) 2024, Owner.\r\n\xff";
        let repaired = b"\xef\xbb\xbf# coding: utf-8\r\n# Copyright (C) 2024-2030, Owner.\r\n\xff";
        fs::write(&path, original).unwrap();
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            fs::set_permissions(&path, Permissions::from_mode(0o754)).unwrap();
        }
        let before = stamp(&fs::metadata(&path).unwrap()).unwrap();
        let snapshot = read(&path, root.path()).unwrap();
        assert!(snapshot.unsafe_reason.is_none());
        replace(&path, &snapshot, original, root.path()).unwrap();
        assert_eq!(stamp(&fs::metadata(&path).unwrap()).unwrap(), before);
        replace(&path, &snapshot, repaired, root.path()).unwrap();
        assert_eq!(fs::read(&path).unwrap(), repaired);
        #[cfg(unix)]
        assert_eq!(fs::metadata(&path).unwrap().mode() & 0o7777, 0o754);
        assert_eq!(fs::read_dir(root.path()).unwrap().count(), 1);
    }

    #[test]
    fn changed_content_and_same_content_replacements_are_refused() {
        let root = tempfile::tempdir().unwrap();
        let path = root.path().join("source.py");
        fs::write(&path, b"old").unwrap();
        let original = read(&path, root.path()).unwrap();
        fs::write(&path, b"new").unwrap();
        assert!(matches!(
            replace(&path, &original, b"repair", root.path()),
            Err(RepairError::Unsafe(_))
        ));
        assert_eq!(fs::read(&path).unwrap(), b"new");
        let snapshot = read(&path, root.path()).unwrap();
        let temporary = root.path().join("replacement.py");
        fs::write(&temporary, b"new").unwrap();
        fs::rename(&temporary, &path).unwrap();
        assert!(matches!(
            replace(&path, &snapshot, b"repair", root.path()),
            Err(RepairError::Unsafe(_))
        ));
        assert_eq!(fs::read(&path).unwrap(), b"new");
        assert_eq!(fs::read_dir(root.path()).unwrap().count(), 1);
    }

    #[test]
    fn hard_links_are_readable_but_never_repaired() {
        let root = tempfile::tempdir().unwrap();
        let path = root.path().join("source.py");
        let alias = root.path().join("alias.py");
        fs::write(&path, b"original").unwrap();
        fs::hard_link(&path, &alias).unwrap();
        let snapshot = read(&path, root.path()).unwrap();
        assert_eq!(snapshot.bytes, b"original");
        assert!(
            snapshot
                .unsafe_reason
                .as_ref()
                .unwrap()
                .contains("hard links")
        );
        assert!(matches!(
            replace(&path, &snapshot, b"repaired", root.path()),
            Err(RepairError::Unsafe(_))
        ));
        assert_eq!(fs::read(alias).unwrap(), b"original");
    }

    #[cfg(unix)]
    #[test]
    fn symlinks_are_not_traversed_or_repaired() {
        use std::os::unix::fs::symlink;
        let root = tempfile::tempdir().unwrap();
        let source = root.path().join("source");
        fs::create_dir(&source).unwrap();
        let target = root.path().join("target.py");
        fs::write(&target, b"original").unwrap();
        let file_link = source.join("link.py");
        symlink(&target, &file_link).unwrap();
        let directory_link = root.path().join("link");
        symlink(&source, &directory_link).unwrap();
        let mut settings = settings(root.path());
        settings.paths = vec![source.clone()];
        assert!(discover(&settings).unwrap().is_empty());
        settings.paths = vec![directory_link.clone()];
        assert!(
            discover(&settings)
                .unwrap_err()
                .contains("Refusing symlink")
        );
        settings.paths = vec![file_link.clone()];
        assert_eq!(discover(&settings).unwrap(), vec![file_link.clone()]);
        let original = read(&file_link, root.path()).unwrap();
        assert_eq!(original.bytes, b"original");
        assert!(matches!(
            replace(&file_link, &original, b"repaired", root.path()),
            Err(RepairError::Unsafe(_))
        ));
        let plain_file = source.join("plain.py");
        fs::write(&plain_file, b"original").unwrap();
        for path in [
            directory_link.join("plain.py"),
            directory_link.join("../target.py"),
        ] {
            let original = read(&path, root.path()).unwrap();
            assert!(original.unsafe_reason.unwrap().contains("parent"));
        }
        assert_eq!(fs::read(target).unwrap(), b"original");
    }
}
