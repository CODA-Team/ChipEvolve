# Generic native inventory from the original flow, with no directed targets.
proc inventory {prefix} {
  set b [ord::get_db_block]
  set f [open ${prefix}.design.tsv w]
  set die [$b getDieArea]; set core [$b getCoreArea]
  puts $f [join [list [$b getName] [$b getDbUnitsPerMicron] [llength [$b getInsts]] [llength [$b getNets]] [llength [$b getBTerms]] [$die xMin] [$die yMin] [$die xMax] [$die yMax] [$core xMin] [$core yMin] [$core xMax] [$core yMax]] \t]
  close $f
  set f [open ${prefix}.instances.tsv w]
  set m [open ${prefix}.macros.tsv w]
  foreach i [$b getInsts] {
    set master [$i getMaster]; set rect [$i getBBox]; lassign [$i getLocation] x y
    set row [join [list [$i getName] [$i getId] [$master getName] [$master isBlock] [$i getOrient] $x $y [$rect xMin] [$rect yMin] [$rect xMax] [$rect yMax] [llength [$i getITerms]]] \t]
    puts $f $row
    if {[$master isBlock]} {puts $m $row}
  }
  close $f; close $m
  set f [open ${prefix}.nets.tsv w]
  set p [open ${prefix}.macro_pins.tsv w]
  foreach n [$b getNets] {
    set drivers {}; set loads {}; set macro_loads {}; set macro_drivers {}
    foreach t [$n getITerms] {
      set i [$t getInst]; set mt [$t getMTerm]
      set name "[$i getName]/[$mt getName]"
      if {[$mt getIoType] eq "OUTPUT"} {
        lappend drivers $name
        if {[[$i getMaster] isBlock]} {lappend macro_drivers $name}
      } else {
        lappend loads $name
        if {[[$i getMaster] isBlock]} {lappend macro_loads $name}
      }
      if {[[$i getMaster] isBlock]} {
        puts $p [join [list $name [$t getId] [$i getName] [$mt getName] [$mt getIoType] [$mt getSigType] [$n getName]] \t]
      }
    }
    foreach t [$n getBTerms] {
      if {[$t getIoType] eq "INPUT"} {lappend drivers [$t getName]} else {lappend loads [$t getName]}
    }
    puts $f [join [list [$n getName] [$n getId] [$n getSigType] [llength $loads] [join [lsort $drivers] \x1e] [join [lsort $loads] \x1e] [join [lsort $macro_drivers] \x1e] [join [lsort $macro_loads] \x1e]] \t]
  }
  close $f; close $p
  set f [open ${prefix}.clocks.tsv w]
  foreach c [all_clocks] {
    puts $f [join [list [get_name $c] [$c period] [$c is_virtual] [$c is_propagated]] \t]
  }
  close $f
}


inventory inventory
