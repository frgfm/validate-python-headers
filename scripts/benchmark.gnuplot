# Copyright (C) 2026, François-Guillaume Fernandez.
# This program is licensed under the Apache License 2.0.
# See LICENSE or go to <https://www.apache.org/licenses/LICENSE-2.0> for full license details.

data_dir = system("printenv BENCH_DATA")
output_dir = system("printenv BENCH_OUTPUT")
bytes = int(system("printenv BENCH_BYTES"))
largest = int(system("printenv BENCH_MAX"))
set encoding utf8
set datafile separator "\t"
set border 0
set tics nomirror scale 0 textcolor rgb "#657086"
set lmargin at screen .15
set rmargin at screen .94
set style fill solid 1 noborder
set boxwidth .55 relative
do for [format in "svg png"] {
    scale = format eq "svg" ? 1 : 1.5
    title_font = sprintf("sans,%d",26*scale)
    key_font = sprintf("sans,%d",12*scale)
    panel_font = sprintf("sans,%d",16*scale)
    do for [chart in "check fix"] {
        file = data_dir."/".chart.".dat"
        set xrange [*:*]; set yrange [*:*]
        stats file using 1 nooutput
        panels = STATS_blocks
        height = panels*250+180
        if (format eq "svg") { set terminal svg size 800,height dynamic enhanced font "sans,12" }
        if (format eq "png") { set terminal pngcairo size 1200,height*1.5 enhanced font "sans,18" }
        set output output_dir."/".chart.".".format
        set lmargin at screen .15
        set label 1 (chart eq "check" ? "{/:Bold How much time does a check add?}" : "{/:Bold How long does a full year update take?}") at screen .08,1-42.0/height font title_font tc rgb "#172033"
        set label 10 sprintf("Native CLI · JSON · %d bytes/file · warm synthetic sources",bytes) at screen .08,1-84.0/height font key_font tc rgb "#657086"
        set label 11 "Independent vertical scales · all start at zero · lower is faster" at screen .08,30.0/height font key_font tc rgb "#657086"
        unset key
        unset xlabel
        unset ylabel
        set format y "%g ms"
        set xtics autofreq nomirror scale 0 font key_font
        set ytics autofreq nomirror scale 0
        unset grid
        set grid ytics back lc rgb "#edf0f5"
        set multiplot
        do for [panel=0:panels-1] {
            set xrange [*:*]; set yrange [*:*]
            stats file index panel using 1:3 nooutput
            count = int(STATS_min_x)
            count_label = count>=1000 && count<1000000 && count%1000==0 ? sprintf("%g,000",count/1000) : sprintf("%g",count)
            set title sprintf("{/:Bold %s file%s}%s",count_label,count==1 ? "" : "s",count<9 ? " per language · LMH" : " · mixed languages") font panel_font tc rgb "#172033"
            set tmargin at screen (1-(160.0+panel*250)/height)
            set bmargin at screen (1-(310.0+panel*250)/height)
            set xrange [-.6:STATS_records-.4]
            set yrange [0:STATS_max_y*1.28]
            set xtics rotate by (STATS_records>3 ? -35 : 0)
            plot file index panel using 0:3:($4==1 ? 0x6554df : $4==2 ? 0x078b79 : 0x7c899d) with boxes lc rgb variable notitle, \
                 file index panel using 0:3:(sprintf("%g ms",$3)):xtic(2) with labels offset char 0,1 font key_font tc rgb "#172033" notitle
            unset label 1
            unset label 10
            unset label 11
        }
        unset multiplot
        unset output
    }
    file = data_dir."/memory.dat"
    set xrange [*:*]; set yrange [*:*]
    stats file using 2 nooutput
    if (format eq "svg") { set terminal svg size 1100,620 dynamic enhanced font "sans,12" }
    if (format eq "png") { set terminal pngcairo size 1650,930 enhanced font "sans,18" }
    set output output_dir."/memory.".format
    unset title
    set label 1 "{/:Bold How much memory will it need?}" at screen .08,.93 font title_font tc rgb "#172033"
    set label 10 sprintf("Native CLI · JSON · %d bytes/file · warm synthetic sources",bytes) at screen .08,.84 font key_font tc rgb "#657086"
    set label 11 sprintf("LMH · %d files · peak RSS · harness/build memory excluded",largest) at screen .08,.04 font key_font tc rgb "#657086"
    set key at screen .11,.79 left top horizontal reverse Left nobox font key_font
    set lmargin at screen .11
    set tmargin at screen .72
    set bmargin at screen .18
    set xtics autofreq nomirror scale 0 rotate by 0 font key_font
    set ytics autofreq nomirror scale 0
    unset grid
    set grid xtics back lc rgb "#edf0f5"
    set format x "%g"
    set format y "%g"
    set xlabel "Peak native-process RSS (MiB)"
    set xrange [0:*]
    set yrange [STATS_records-.5:-.5]
    plot file using 2:($0-.18):ytic(1) with points pt 7 ps 1.3 lc rgb "#6554df" title "Routine check", \
         file using 3:0 with points pt 7 ps 1.3 lc rgb "#7c899d" title "Check with findings", \
         file using 4:($0+.18) with points pt 7 ps 1.3 lc rgb "#078b79" title "Repair"
    unset output
    unset ytics
    set ytics autofreq
    unset label 1
    unset label 10
    unset label 11
}
