// PNLF for WhateverXe's internal-panel brightness (WhateverXe README, "Internal-panel brightness"). UID 19 is
// the only one its backlight profile accepts (kern_backlight_profile.hpp: uid 19, range 0..65535); WhateverXe drives
// the PCH PWM itself, so nothing here touches registers. Created only for macOS, as every Acer SSDT here.
DefinitionBlock ("", "SSDT", 2, "ACER", "ANVPNLF", 0x00000001)
{
    If (_OSI ("Darwin"))
    {
        Device (\_SB.PNLF)
        {
            Name (_HID, EisaId ("APP0002"))
            Name (_CID, "backlight")
            Name (_UID, 0x13)
            Method (_STA, 0, NotSerialized)
            {
                Return (0x0B)
            }
        }
    }
}
