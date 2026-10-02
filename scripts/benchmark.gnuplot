# Copyright (C) 2026, François-Guillaume Fernandez.
# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

data_dir = system("printenv BENCH_DATA")
output_dir = system("printenv BENCH_OUTPUT")
bytes = int(system("printenv BENCH_BYTES"))
largest = int(system("printenv BENCH_MAX"))
set encoding utf8
set border 0
set tics nomirror scale 0 textcolor rgb "#657086"
set key at screen .11,.79 left top horizontal maxrows 2 reverse Left nobox font ",12"
set lmargin at screen .11
set rmargin at screen .94
set tmargin at screen .72
set bmargin at screen .18
set label 10 sprintf("Native CLI · JSON output · %d bytes/file · synthetic · warm cache",bytes) at screen .08,.84 font ",12" tc rgb "#657086"
set label 11 "Measured medians · lines connect measured sizes; no extrapolation" at screen .08,.04 font ",11" tc rgb "#657086"
do for [format in "svg png"] {
    if (format eq "svg") { set terminal svg size 1100,620 dynamic enhanced font "sans,12" }
    if (format eq "png") { set terminal pngcairo size 1650,930 enhanced font "sans,18" }
    scale = format eq "svg" ? 1 : 1.5
    title_font = sprintf("sans,%d",26*scale)
    caption_font = sprintf("sans,%d",11*scale)
    key_font = sprintf("sans,%d",12*scale)
    set key font key_font
    set label 10 font key_font
    do for [chart in "check fix"] {
        file = data_dir."/".chart.".dat"
        set output output_dir."/".chart.".".format
        set label 1 (chart eq "check" ? "{/:Bold How much time does a check add?}" : "{/:Bold How long does a full year update take?}") at screen .08,.93 font title_font tc rgb "#172033"
        set label 11 "Measured medians · lines connect measured sizes; no extrapolation" at screen .08,.04 font caption_font tc rgb "#657086"
        set xtics autofreq nomirror scale 0 textcolor rgb "#657086"
        set ytics autofreq nomirror scale 0 textcolor rgb "#657086"
        unset logscale x
        set autoscale
        stats file using 1 nooutput
        array ticks[STATS_records]
        stats file using (ticks[$0+1]=$1) nooutput
        set xtics ()
        do for [i=1:|ticks|] { set xtics add (sprintf("%g",ticks[i]) ticks[i]) }
        set logscale x
        unset grid
        set grid ytics back lc rgb "#edf0f5"
        set format x "%g"
        set format y "%g ms"
        set xlabel "Files selected for this invocation"
        set ylabel "Elapsed wall-clock time"
        set xrange [0.75:largest*1.5]
        set yrange [0:*]
        plot file using 1:5:6 with filledcurves lc rgb "#e6e9f2" title "LMH · range across nine languages", \
             file using 1:(($5+$6)/2):5:6 with yerrorbars pt 0 lw 2 lc rgb "#c6cadb" notitle, \
             file using 1:2 with linespoints lw 3 pt 7 ps 1.1 lc rgb "#6554df" title "LMH · mixed", \
             file using 1:3 with linespoints lw 3 pt 7 ps 1.1 lc rgb "#078b79" title "HawkEye · mixed", \
             file using 1:4 with linespoints lw 3 pt 7 ps 1.1 lc rgb "#7c899d" title "LMH before · mixed"
        unset output
    }
    file = data_dir."/memory.dat"
    unset logscale x
    set autoscale
    stats file using 2 nooutput
    set output output_dir."/memory.".format
    set label 1 "{/:Bold How much memory will it need?}" at screen .08,.93 font title_font tc rgb "#172033"
    set label 11 sprintf("LMH · %d files · peak native RSS · harness/build memory excluded",largest) at screen .08,.04 font caption_font tc rgb "#657086"
    unset logscale x
    set xtics autofreq nomirror scale 0 textcolor rgb "#657086"
    unset grid
    set grid xtics back lc rgb "#edf0f5"
    set format x "%g"
    set format y "%g"
    set xlabel "Peak native-process RSS (MiB)"
    unset ylabel
    set xrange [0:*]
    set yrange [STATS_records-.5:-.5]
    plot file using 2:($0-.18):ytic(1) with points pt 7 ps 1.3 lc rgb "#6554df" title "Routine check", \
         file using 3:0 with points pt 7 ps 1.3 lc rgb "#7c899d" title "Check with findings", \
         file using 4:($0+.18) with points pt 7 ps 1.3 lc rgb "#078b79" title "Repair"
    unset output
    unset ytics
    set ytics autofreq
}
