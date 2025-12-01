![image](https://github.com/ArikShemesh/ha-simple-timer/blob/main/custom_components/simple_timer/brands/simple_timer/logo.png)


# HA Simple Timer Integration (+ Card)
A simple Home Assistant integration that turns entities on and off with a precise countdown timer and daily runtime tracking.

<a href="https://coff.ee/codemakor" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/white_img.png" alt="Buy Me A Coffee" style="height: auto !important;width: auto !important;" ></a>

![image](https://github.com/ArikShemesh/ha-simple-timer/blob/main/images/simple_timer_dashboard.png)

### Configuration
![image](https://github.com/ArikShemesh/ha-simple-timer/blob/main/images/simple_timer_card_configuration.png)

## ✨ Key Features
🚀 **Out-of-the-box**, pre-packaged timer solution, eliminating manual creation of multiple Home Assistant entities, sensors, and automations.

🕐 **Precise Timer Control** - Set countdown timers from 1-1000 minutes for any switch, input_boolean, light, or fan

📊 **Daily Runtime Tracking** - Automatically tracks and displays daily usage time

🔄 **Smart Auto-Cancel** - Timer automatically cancels if the controlled device is turned off externally

🎨 **Professional Timer Card** - Beautiful, modern UI with customizable timer buttons and real-time countdown

🔔 **Notification Support** - Optional notifications for timer start, finish, and cancellation events

🌙 **Midnight Reset** - Daily usage statistics reset automatically at midnight

⏰ **Delayed Start Timers** - Turns devices ON when timer completes and keeps them on indefinitely until manually turned off

## 🏠 Perfect For

- **Water Heater Control** - Manage boiler schedules  
- **Kitchen Timers** - Control smart switches for appliances
- **Garden Irrigation** - Time watering systems
- **Lighting Control** - Automatic light timers
- **Fan Control** - Bathroom or ventilation fans
- **Any Timed Device** - Universal timer for any switchable device

## 📦 Installation

### HACS (Recommended)

⚠️ If you previously added this integration as a custom repository in HACS, it's recommended to remove the custom entry and reinstall it from the official HACS store.
You will continue to receive updates in both cases, but switching ensures you're aligned with the official listing and avoids potential issues in the future.

Use this link to open the repository in HACS and click on Download

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ArikShemesh&repository=ha-simple-timer)

### Manual Installation
1. Download the latest release from [GitHub Releases](https://github.com/ArikShemesh/ha-simple-timer/releases)
2. Extract the `custom_components/simple_timer` folder to your Home Assistant `custom_components` directory
3. **Restart Home Assistant**

**That's it!** The timer card is automatically installed and ready to use - no additional steps required.

## ⚙️ Configuration

### Add Integration Instance
1. Go to **Settings → Devices & Services**
2. Click **"Add Integration"**
3. Search for **"Simple Timer"**
4. Select the device you want to control (switch, light, fan, input_boolean)
5. Give your timer instance a descriptive name (e.g., "Kitchen Timer", "Water Heater")
6. Choose notification entitiy (optional) - can be add more than one
7. Check show seconds (optional) - display seconds in uasge time and notifications

### Add Timer Card to Dashboard
1. **Edit your dashboard**
2. **Add a card**
3. Search for **"Simple Timer Card"** (should appear in the card picker)
4. **Configure the card:**
   - Select your timer instance
   - Customize timer buttons
   - Add a custom card title (optional)
  
## 🔄 Renaming Timer Instances

### ✅ Recommended Method
1. Go to **Settings → Devices & Services**  
2. Find your Simple Timer integration
3. Click **Configure** (⚙️ gear icon)
4. Change the name and save

### 💡 Note on 3-Dots Rename
If you use the 3-dots menu to rename, open **Configure** once afterward to sync the change.

## 🎛️ Card Configuration

### Visual Configuration (Recommended)
Use the card editor in the Home Assistant UI for easy configuration.

### YAML Configuration
```yaml
type: custom:timer-card
timer_instance_id: your_instance_entry_id
timer_buttons: [15, 30, 60, 90, 120, 150]
card_title: "Kitchen Timer"
slider_max: 120
reverse_mode: true
show_daily_usage: true
power_icon: "mdi:power"
```

### Configuration Options

Option                | Type     | Default                  | Description
----------------------|----------|--------------------------|-------------------------------------------------------
`type`                | string   | -                        | Must be `custom:timer-card`
`timer_instance_id`   | string   | -                        | Entry ID of your timer instance
`timer_buttons`       | array    | [15,30,60,90,120,150]    | Timer duration buttons (1-1000 minutes)
`card_title`          | string   | -                        | Custom title for the card
`slider_max`          | integer  | 120                      | Slider max value (1-1000 minutes)
`reverse_mode`        | boolean  | false                    | Enable or disabled the delayed start feature
`show_daily_usage`    | boolean  | false                    | Display or hide the daily usage
`power_icon`          | mdi      | mdi:power                | Set the power button icon

## ❓ Frequently Asked Questions

### Can I have multiple timer instances?
Yes! Add multiple integrations for different devices.

### Does the timer work if Home Assistant restarts?
Yes, active timers resume automatically with offline time compensation.

### Can I customize the timer buttons?
Yes, configure any timer value between 1-1000 `timer_buttons: [7, 13, 25, 1000]` in the card YAML.

### Why does my usage show a warning message?
This appears when HA was offline during a timer to indicate potential time sync issues.

## 🚨 Troubleshooting

### Card Not Appearing in Card Picker

1. **Restart Home Assistant:** The card is installed during integration setup
2. **Check integration logs:** Look for any errors during the card installation process
3. **Verify automatic installation:** Check if `/config/www/simple-timer/timer-card.js` exists
4. **Clear browser cache:** Hard refresh with Ctrl+F5 (Windows) or Cmd+Shift+R (Mac)
5. **Check browser console:** Press F12 and look for JavaScript errors

### Timer Not Working

1. **Check device entity:** Ensure the controlled device exists and is accessible
2. **Verify integration setup:** Go to Settings → Devices & Services → Simple Timer
3. **Check logs:** Look for errors in Settings → System → Logs
4. **Restart integration:** Remove and re-add the integration if needed

### Daily Usage Not Tracking

1. **Device state changes:** Timer only tracks when the device is actually ON
2. **Manual control:** If you turn the device off manually, tracking stops (by design)
3. **Midnight reset:** Usage resets at 00:00 each day automatically

### Card Installation Issues

If the automatic card installation fails:
1. **Check file permissions:** Ensure Home Assistant can write to the `www` directory
2. **Verify disk space:** Ensure sufficient space for file copying
3. **Check integration logs:** Look for specific error messages
4. **Manual fallback:** You can still manually copy the card file from the integration's `dist` folder

## 📝 Getting Help

If you encounter issues:

1. **Check the [Issues](https://github.com/ArikShemesh/ha-simple-timer/issues)** page for existing solutions
2. **Enable debug logging:**
   ```yaml
   logger:
     logs:
       custom_components.simple_timer: debug
   ```
3. **Create a new issue** with:
   - Home Assistant version
   - Integration version
   - Detailed error description
   - Relevant log entries

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⭐ Support

If you find this integration useful, please consider:
- ⭐ **Starring this repository**
- 🐛 **Reporting bugs** you encounter
- 💡 **Suggesting new features**
- 📖 **Improving documentation**

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=ArikShemesh/ha-simple-timer&type=date&legend=top-left)](https://www.star-history.com/#ArikShemesh/ha-simple-timer&type=date&legend=top-left)

**Made with ❤️ for the Home Assistant community**
