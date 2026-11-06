// Acer ANV15-52: native EC0 is retained; synthetic EC has no hardware regions.
// Reference: OpenCore AcpiSamples/SSDT-EC-USBX.dsl and Dortania laptop sample.
DefinitionBlock ("", "SSDT", 2, "ACER", "ANVECUSB", 0x00000001)
{
    External (_SB_.PC00.LPCB, DeviceObj)
    If (_OSI ("Darwin"))
    {
        Scope (\_SB.PC00.LPCB)
        {
            Device (EC)
            {
                Name (_HID, "ACID0001")
                Method (_STA, 0, NotSerialized)
                {
                    If (_OSI ("Darwin")) { Return (0x0F) }
                    Return (Zero)
                }
            }
        }
        Scope (\_SB)
        {
            Device (USBX)
            {
                Name (_ADR, Zero)
                Method (_STA, 0, NotSerialized)
                {
                    If (_OSI ("Darwin")) { Return (0x0F) }
                    Return (Zero)
                }
                Method (_DSM, 4, NotSerialized)
                {
                    If (Arg2 == Zero) { Return (Buffer (One) { 0x03 }) }
                    Return (Package (0x08) {
                        "kUSBSleepPowerSupply", 0x13EC,
                        "kUSBSleepPortCurrentLimit", 0x0834,
                        "kUSBWakePowerSupply", 0x13EC,
                        "kUSBWakePortCurrentLimit", 0x0834
                    })
                }
            }
        }
    }
}
