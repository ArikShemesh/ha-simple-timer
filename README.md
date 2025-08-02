![image](https://github.com/ArikShemesh/ha-simple-timer/blob/main/custom_components/simple_timer/brands/simple_timer/logo.png)


# HA Simple Timer Integration (+ Card)
A simple Home Assistant integration that turns entities on and off with a precise countdown timer and daily runtime tracking.

<a href="https://coff.ee/codemakor" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/white_img.png" alt="Buy Me A Coffee" style="height: auto !important;width: auto !important;" ></a>

![image](https://github.com/ArikShemesh/ha-simple-timer/blob/main/images/simple_timer_card.png)

## ✨ Key Features
🚀 **Out-of-the-box**, pre-packaged timer solution, eliminating manual creation of multiple Home Assistant entities, sensors, and automations.

🕐 **Precise Timer Control** - Set countdown timers from 1-1000 minutes for any switch, input_boolean, light, or fan

📊 **Daily Runtime Tracking** - Automatically tracks and displays daily usage time in HH:MM format

🔄 **Smart Auto-Cancel** - Timer automatically cancels if the controlled device is turned off externally

🎨 **Professional Timer Card** - Beautiful, modern UI with customizable timer buttons and real-time countdown

🔔 **Notification Support** - Optional notifications for timer start, finish, and cancellation events

🌙 **Midnight Reset** - Daily usage statistics reset automatically at midnight

## 🏠 Perfect For

- **Water Heater Control** - Manage boiler schedules  
- **Kitchen Timers** - Control smart switches for appliances
- **Garden Irrigation** - Time watering systems
- **Lighting Control** - Automatic light timers
- **HVAC Management** - Climate control scheduling
- **Fan Control** - Bathroom or ventilation fans
- **Any Timed Device** - Universal timer for any switchable device

## 📦 Installation

## Step 1: Integration Install

### HACS

⚠️ If you previously added this integration as a custom repository in HACS, it's recommended to remove the custom entry and reinstall it from the official HACS store.
You will continue to receive updates in both cases, but switching ensures you're aligned with the official listing and avoids potential issues in the future.

Use this link to open the repository in HACS and click on Download

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ArikShemesh&repository=ha-simple-timer)

### Manual Installation
1. Download the latest release from [GitHub Releases](https://github.com/ArikShemesh/ha-simple-timer/releases)
2. Extract the `custom_components/simple_timer` folder to your Home Assistant `custom_components` directory
3. **Restart Home Assistant**

## Step 2: Install the Timer Card (Manual)

Since HACS only downloads the integration files, you need to manually install the timer card:

1. **Download the card file:**
   - Go to the [latest release](https://github.com/ArikShemesh/ha-simple-timer/releases/latest)
   - Download `timer-card.js` from the `dist` folder

2. **Create the directory structure:**
   ```
   config/
   └── www/
        └── ha-simple-timer/
            └── timer-card.js       ← Place file here
   ```

3. **Add reference to: `timer-card.js`**

- **Using UI:** _Settings_ → _Dashboards_ → _More Options icon_ → _Resources_ → _Add Resource_ → Set _Url_ as `/local/ha-simple-timer/timer-card.js` → Set _Resource type_ as `JavaScript Module`.

_or_
  
- **Edit your `configuration.yaml`** and add:
  ```yaml
  lovelace:
   resources:
     - url: /local/ha-simple-timer/timer-card.js
       type: module
  ```

5. **Restart Home Assistant**

6. **Clear browser cache** (Ctrl+F5 or Cmd+Shift+R)

## ⚙️ Configuration

### Add Integration Instance
1. Go to **Settings → Devices & Services**
2. Click **"Add Integration"**
3. Search for **"Simple Timer"**
4. Select the device you want to control (switch, light, fan, input_boolean)
5. Give your timer instance a descriptive name (e.g., "Kitchen Timer", "Water Heater")

### Add Timer Card to Dashboard
1. **Edit your dashboard**
2. **Add a card**
3. Search for **"Simple Timer Card"** (should appear in the card picker)
4. **Configure the card:**
   - Select your timer instance
   - Customize timer buttons
   - Set optional notification entity
   - Add a custom card title
  
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
notification_entity: notify.mobile_app_your_phone
show_seconds: true  # Optional: show HH:MM:SS format
```

### Configuration Options

Option                | Type     | Required | Default                  | Description
----------------------|----------|----------|--------------------------|-------------------------------------------------------
`type`                | string   | ✅       | -                        | Must be `custom:timer-card`
`timer_instance_id`   | string   | ✅       | -                        | Entry ID of your timer instance
`timer_buttons`       | array    | ❌       | [15,30,60,90,120,150]    | Timer duration buttons (1-1000 minutes)
`card_title`          | string   | ❌       | -                        | Custom title for the card
`notification_entity` | string   | ❌       | -                        | Notification service for timer alerts
`show_seconds`        | boolean  | ❌       | false                    | Show seconds in time display (HH:MM:SS vs HH:MM)

## ❓ Frequently Asked Questions

### Can I have multiple timer instances?
Yes! Add multiple integrations for different devices.

### Does the timer work if Home Assistant restarts?
Yes, active timers resume automatically with offline time compensation.

### Can I customize the timer buttons?
Yes, configure `timer_buttons: [5, 10, 15, 30, 45, 60]` in the card YAML.

### Why does my usage show a warning message?
This appears when HA was offline during a timer to indicate potential time sync issues.

## 🚨 Troubleshooting

### Card Not Appearing in Card Picker

1. **Verify file location:** Ensure `timer-card.js` is in `/config/www/ha-simple-timer/`
2. **Check resource configuration:** Verify the resource URL in `configuration.yaml`
3. **Clear browser cache:** Hard refresh with Ctrl+F5 (Windows) or Cmd+Shift+R (Mac)
4. **Check browser console:** Press F12 and look for JavaScript errors
5. **Restart Home Assistant:** Sometimes needed after adding resources

### Timer Not Working

1. **Check device entity:** Ensure the controlled device exists and is accessible
2. **Verify integration setup:** Go to Settings → Devices & Services → Simple Timer
3. **Check logs:** Look for errors in Settings → System → Logs
4. **Restart integration:** Remove and re-add the integration if needed

### Daily Usage Not Tracking

1. **Device state changes:** Timer only tracks when the device is actually ON
2. **Manual control:** If you turn the device off manually, tracking stops (by design)
3. **Midnight reset:** Usage resets at 00:00 each day automatically

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

**Made with ❤️ for the Home Assistant community**
