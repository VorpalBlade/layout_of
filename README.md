# GDB extension to display layout of a type

This is a pair of simple GDB commands to display layout of types. There are two
commands in this repo:

* `layout-of [-r] TYPE_NAME` displays the memory layout of `TYPE_NAME`,
  optionally showing details recursively. It will show byte ranges for each
  member as well as any holes due to padding.
* `offsets-of TYPE_NAME` will just show the starting offset of each member.

## Example

Below is an example of using the commands in Rust (they work for C and C++ as
well, other languages are untested).

**NOTES!**
* For Rust, the command might not be accurate for types with niches, which
  mostly affects enums, but the commands should be correct for structs.
* For Rust, the total padding can be wrong with enums, as it can get double
  counted. Unions in C and C++ could have the same issue, but those are much
  less commonly used than enums in Rust.
* If the type of interest contains spaces put quotes around the argument


Please be aware that in the real terminal,
colours will be used to enhance readability (not visible here in the README).

```
(gdb) offsets-of ini_merge::Property
ini_merge::Property {
    section => 0
    key => 16
    val => 48
    raw => 32
}

(gdb) layout-of ini_merge::Property
ini_merge::Property {
   section => 0 - 16
   key => 16 - 32
   raw => 32 - 48
   val => 48 - 64
}
Total size: 64

(gdb) layout-of -r ini_merge::Property
ini_merge::Property {
   section => 0 - 16 (&str) {
      data_ptr => 0 - 8
      length => 8 - 16
   }
   key => 16 - 32 (&str) {
      data_ptr => 0 - 8
      length => 8 - 16
   }
   raw => 32 - 48 (&str) {
      data_ptr => 0 - 8
      length => 8 - 16
   }
   val => 48 - 64 (core::option::Option<&str>) {
      None => 0 - 8
      None => 0 - 16 (core::option::Option<&str>::None) {

         --- Padding: 16 bytes ---   

      }
      Some => 0 - 16 (core::option::Option<&str>::Some) {
         __0 => 0 - 16 (&str) {
            data_ptr => 0 - 8
            length => 8 - 16
         }
      }
   }
}
Total padding size: 16
Total size: 64

(gdb) layout-of "ini_merge::actions::Actions<ini_merge::filter::FilterAction, ini_merge::filter::FilterAction>"
ini_merge::actions::Actions<ini_merge::filter::FilterAction, ini_merge::filter::FilterAction> {
   section_actions => 0 - 48
   literal_actions => 48 - 96
   regex_matches => 96 - 128
   regex_actions => 128 - 152
}
Total size: 152
```

## Installation

First, you should install the ansicolors package for the Python version
your GDB uses. For example:

```bash
# Install with pip:
pip install -U --user ansicolors
# Install using pacman on Arch Linux:
sudo pacman -S python-ansicolors
```

In your .gdbinit add:

```
python
import sys
sys.path.insert(0, '<absolute checkout path of this repo>')
import layout_of
end
```
