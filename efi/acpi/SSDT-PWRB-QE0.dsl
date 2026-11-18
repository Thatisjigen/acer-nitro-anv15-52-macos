// Acer ANV15-52, macOS only, for the sleep in S0: delivers the power button to macOS.
// The EC reports a press as query _QE0, which the firmware forwards only to HIDD (Intel HID event filter) once the
// Windows driver has called HIDD.BTNL; on macOS that never happens, so AppleACPIButton on PWRB never sees a press.
// Needs the OpenCore DSDT patch _QE0 -> XQE0 (Method header 14 26 5F 51 45 30, one occurrence at 0x1EBCA of the
// 232164-byte ACRPRDCT DSDT). Also gives PWRB a wake GPE (the EC's SCI, GPE 0x6E = EC0._GPE), so a press can wake
// the PC from sleep; every other EC event shares that GPE.
DefinitionBlock ("", "SSDT", 2, "ACER", "ANVPBQE0", 0x00000001)
{
    External (_SB_.PWRB, DeviceObj)
    External (_SB_.PC00.LPCB.EC0, DeviceObj)

    If (_OSI ("Darwin"))
    {
        Scope (\_SB.PWRB)
        {
            Name (_PRW, Package (0x02)
            {
                0x6E,
                0x03
            })
        }

        Scope (\_SB.PC00.LPCB.EC0)
        {
            Method (_QE0, 0, NotSerialized)
            {
                Notify (\_SB.PWRB, 0x80)
            }
        }
    }
}
