// 20 Processor objects, created
// unconditionally like OpenCore SSDT-PLUG-ALT; each _STA still returns 0 outside Darwin.
// Injected only through the OpenCore entry, Linux/Windows boot from rEFInd.
DefinitionBlock ("", "SSDT", 2, "ACER", "ANVPLUG", 0x00000001)
{
    Scope (\_SB)
    {
        Processor (CP00, 0x00, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 0)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
            Method (_DSM, 4, NotSerialized)
            {
                If (Arg2 == Zero) { Return (Buffer (One) { 0x03 }) }
                Return (Package (0x02) { "plugin-type", One })
            }
        }
        Processor (CP01, 0x01, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 1)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
        Processor (CP02, 0x02, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 2)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
        Processor (CP03, 0x03, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 3)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
        Processor (CP04, 0x04, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 4)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
        Processor (CP05, 0x05, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 5)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
        Processor (CP06, 0x06, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 6)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
        Processor (CP07, 0x07, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 7)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
        Processor (CP08, 0x08, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 8)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
        Processor (CP09, 0x09, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 9)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
        Processor (CP10, 0x0A, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 10)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
        Processor (CP11, 0x0B, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 11)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
        Processor (CP12, 0x0C, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 12)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
        Processor (CP13, 0x0D, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 13)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
        Processor (CP14, 0x0E, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 14)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
        Processor (CP15, 0x0F, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 15)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
        Processor (CP16, 0x10, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 16)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
        Processor (CP17, 0x11, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 17)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
        Processor (CP18, 0x12, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 18)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
        Processor (CP19, 0x13, 0x00000000, 0x00)
        {
            Name (_HID, "ACPI0007")
            Name (_UID, 19)
            Method (_STA, 0, NotSerialized)
            {
                If (_OSI ("Darwin")) { Return (0x0F) }
                Return (Zero)
            }
        }
    }
}
