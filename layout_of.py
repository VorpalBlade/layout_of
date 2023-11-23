"""GDB commands for investigating struct layouts."""

import gdb
import operator
import typing

try:
    import colors
except ImportError:

    class colors(object):
        """Dummy helper class to replace the colors module when missing."""

        @staticmethod
        def color(s, fg=None, bg=None, style=None):
            return s

        @staticmethod
        def bold(x):
            return x

        @staticmethod
        def cyan(x):
            return x

        @staticmethod
        def yellow(x):
            return x

        @staticmethod
        def blue(x):
            return x

        @staticmethod
        def magenta(x):
            return x

        @staticmethod
        def red(x):
            return x

        @staticmethod
        def green(x):
            return x


def resolve_type(argument: str) -> gdb.Type:
    """Attempt to find a relevant GDB type from a string provided by the user.

    :param argument: Input from user.
    :return: The resolved type name.
    """
    try:
        # Just look up the type
        return gdb.lookup_type(argument)
    except gdb.error:
        # Try to parse as a value or variable in some way and get the type of the expression.
        value = gdb.parse_and_eval(argument)
        if value is None:
            # TODO: Can this happen or will parse_and_eval always throw?
            raise gdb.GdbError('Could not resolve "%s" as a type' % argument)
        return value.type.unqualified().strip_typedefs()


class Offsets(gdb.Command):
    """Get member offsets in type."""

    def __init__(self):
        super(Offsets, self).__init__("offsets-of", gdb.COMMAND_DATA)

    def complete(self, text, word):
        return gdb.COMPLETE_SYMBOL

    def invoke(self, arg, from_tty):
        argv = gdb.string_to_argv(arg)
        if len(argv) != 1:
            raise gdb.GdbError("offsets-of takes exactly 1 argument.")

        # Try to resolve type and/or value.
        arg_type = resolve_type(argv[0])

        display_name = argv[0]
        if arg_type.name != argv[0]:
            display_name += " (%s)" % arg_type.name
        print(display_name, "{")
        for field in arg_type.fields():
            if not hasattr(field, "bitpos"):
                print("    %s => ? (static member?)" % field.name)
            else:
                print("    %s => %d" % (field.name, field.bitpos // 8))
        print("}")


# Used for colouring nested {}.
_NESTING_COLOURS = (
    lambda x: x,
    colors.red,
    colors.green,
    colors.blue,
    colors.cyan,
    colors.magenta,
    colors.yellow,
)


class Layouts(gdb.Command):
    """Get memory layout of type.

    layout-of [-r] <type or variable>

    -r prints value struct/class members recursively.
    """

    def __init__(self):
        super(Layouts, self).__init__("layout-of", gdb.COMMAND_DATA)

    def complete(self, text, word):
        return gdb.COMPLETE_SYMBOL

    def invoke(self, arg, from_tty):
        argv = gdb.string_to_argv(arg)
        recursive = False
        if len(argv) == 2:
            if argv[0] == "-r":
                recursive = True
                argv = argv[1:]
        if len(argv) != 1:
            raise gdb.GdbError("Usage: layout-of [-r] <type-or-variable>")

        # Try to resolve type and/or value.
        arg_type = resolve_type(argv[0])

        if arg_type.code != gdb.TYPE_CODE_STRUCT:
            print("%s is not a class or struct" % arg_type.name)
            return

        holes, padding = self._print_type(arg_type, argv[0], recursive)
        if recursive and holes > 0:
            print(colors.red("Total hole size: %d" % holes))
        if recursive and padding > 0:
            print(colors.red("Total padding size: %d" % padding))
        print(colors.green("Total size: %d" % arg_type.sizeof))

    @staticmethod
    def _print_indented(indent: int, text: str):
        """Print the text indented at the specific amount

        :param indent: Indentation level.
        :param text: Text to print.
        """
        print("   " * indent + text)

    def _print_type(
        self, gdb_type: gdb.Type, display_name: str, recursive=False, indent=0
    ) -> typing.Tuple[int, int]:
        """Print the layout of a type.

        :param gdb_type: GDB type
        :param display_name: Display name of type.
        :param recursive: If true, recurse on structs.
        :param indent: Current indentation level (for recursion)

        :return: (total_hole_size, total_padding). Only accurate when recursive
        """
        hole_size = 0
        padding = 0

        # Print header
        if gdb_type.name != display_name:
            display_name += " (%s)" % gdb_type.name
        self._print_indented(
            indent,
            display_name
            + colors.bold(_NESTING_COLOURS[indent % len(_NESTING_COLOURS)](" {")),
        )

        # Go through fields and print members
        prev_end = 0
        for field in sorted(
            (x for x in gdb_type.fields() if hasattr(x, "bitpos")),
            key=operator.attrgetter("bitpos"),
        ):
            byte_pos = field.bitpos // 8
            if prev_end < byte_pos:
                print()
                self._print_indented(
                    indent,
                    colors.red("   --- Hole: %d bytes ---\n" % (byte_pos - prev_end)),
                )
                hole_size += byte_pos - prev_end
            size_str = "%s => %d - %d" % (
                field.name,
                byte_pos,
                byte_pos + field.type.sizeof,
            )
            # If we are recursive AND this is a struct member, make a recursive call, otherwise print normally.
            if (
                recursive
                and field.type
                and field.type.strip_typedefs().code == gdb.TYPE_CODE_STRUCT
            ):
                sub_hole_size, sub_padding = self._print_type(
                    field.type, size_str, recursive, indent=indent + 1
                )
                hole_size += sub_hole_size
                padding += sub_padding
            else:
                self._print_indented(indent, "   " + size_str)
            prev_end = max(prev_end, byte_pos + field.type.sizeof)

        # Print footer
        if gdb_type.sizeof > prev_end:
            print()
            self._print_indented(
                indent,
                colors.red(
                    "   --- Padding: %d bytes ---   \n" % (gdb_type.sizeof - prev_end)
                ),
            )
            padding += gdb_type.sizeof - prev_end
        self._print_indented(
            indent, colors.bold(_NESTING_COLOURS[indent % len(_NESTING_COLOURS)]("}"))
        )

        # Deal with empty base classes here, it has fake padding of 1 byte. An example of this is when you inherit
        # from boost::noncopyable. That one byte is going to overlap with actual data from other members.
        if (
            gdb_type.sizeof == 1
            and len(gdb_type.fields()) == 0
            and padding == 1
            and hole_size == 0
        ):
            return 0, 0
        else:
            return hole_size, padding


# Instantiate commands.
Offsets()
Layouts()
