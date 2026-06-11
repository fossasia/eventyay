# Eventyay Image Handling

This document provides a matrix of how uploaded images (specifically event logos and header images) are consumed and processed across the Eventyay platform. 

## Processing Rules

To optimize page loads and save storage bandwidth, uploaded event logos and header banners are optimized on save:
1. **Header Banner (`logo_image`)**: Capped at **3000px wide**
2. **Event Logo (`event_logo_image`)**: Capped at **1000px wide**
3. **Format**: Re-encoded as Progressive JPEG (85% quality) if no alpha channel, or optimized PNG if an alpha channel is present.
4. **Preservation**: The original raw upload is always preserved alongside the optimized variant (e.g. `logo_original.jpg`), allowing future re-processing or cropping without generation loss.

Because the optimized image is stored as the primary value for `settings.logo_image` and `settings.event_logo_image`, all templates and serializers automatically serve the smaller, optimized variant natively.

## Usage Matrix

### Event Logo (`event_logo_image`)
* **Aspect Ratio:** Preserved
* **Display Behavior:** Max height of 160px. Width scales proportionally.
* **Format Guidelines:** SVG, PNG, WebP, JPEG. PNG/SVG/WebP recommended for transparency.
* **Consumption Points:**
  * **Public Event Page Header:** Displayed in the center of the header if uploaded. Replaces the event name text.
  * **Event Cards / Start Page:** Used as the thumbnail for the event on the organizer's public profile and the main instance index page.
  * **Order Invoices (PDF):** Rendered at the top right of the invoice document.
  * **OpenGraph (og:image) Fallback:** Used for social sharing previews if a dedicated `og_image` is not uploaded.

### Header / Banner Image (`logo_image`)
* **Aspect Ratio:** Cropped
* **Display Behavior:** Cropped to a 320px tall vertical strip via CSS (`object-fit: cover`). The horizontal center of the image is always prioritized.
* **Format Guidelines:** JPEG or WebP recommended.
* **Consumption Points:**
  * **Public Event Page Header:** Acts as the full-width background behind the event title or logo.
  * **Ticket PDF Background:** Can optionally be used as a background on ticket designs depending on the layout.
  * **Widget UI:** Displayed at the top of the embeddable ticket widget.
  * **Email Templates:** Embedded as a thumbnail (`|thumb:'5000x120'`) above the email body.

### OpenGraph Image (`og_image`)
* **Aspect Ratio:** Fixed at 1.91:1 (e.g., 1200 x 630px)
* **Display Behavior:** Displayed natively by social media platforms (Facebook, Twitter, LinkedIn, Slack, etc.) when the event URL is shared.
* **Consumption Points:**
  * `<meta property="og:image">` tags on all public event pages (Tickets, CfP, Schedule).

## Deprecation Notice

* The `logo_image` and `event_logo_image` internal settings keys are confusingly named. `logo_image` refers to the **Header Banner**, and `event_logo_image` refers to the **Event Logo**. These are retained for backwards compatibility with the existing database schema and active event data, but UI labels have been updated to reflect their actual visual usage.
