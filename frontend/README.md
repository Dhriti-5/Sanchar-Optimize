# Sanchar-Optimize Landing Page

## 🎯 Purpose
This landing page serves as the primary testing hub for AI for Bharat 2026 judges. It provides:
- Project overview and value proposition
- 3-step setup guide for the Chrome extension
- Live telemetry dashboard showing system health
- Technical architecture documentation

## 🚀 Deployment Options

### Option 1: AWS S3 + CloudFront (Recommended)
```powershell
# Deploy to S3 bucket with static website hosting
aws s3 sync . s3://sanchar-optimize-landing --exclude "*.md" --exclude "*.zip"
aws s3 website s3://sanchar-optimize-landing --index-document index.html

# Optional: Set up CloudFront for HTTPS and CDN
aws cloudfront create-distribution --origin-domain-name sanchar-optimize-landing.s3-website.ap-south-1.amazonaws.com
```

### Option 2: GitHub Pages
```bash
# Push frontend folder to a gh-pages branch
git subtree push --prefix frontend origin gh-pages
# Your site will be available at: https://yourusername.github.io/sanchar-optimize
```

### Option 3: Netlify (Fastest)
1. Drag and drop the `frontend` folder to [Netlify Drop](https://app.netlify.com/drop)
2. Get instant HTTPS URL
3. Optional: Configure custom domain

### Option 4: AWS Amplify
```bash
# Install Amplify CLI
npm install -g @aws-amplify/cli

# Initialize and publish
amplify init
amplify add hosting
amplify publish
```

## 📦 Extension Preparation

Before deploying, create the extension.zip file:

```powershell
# From project root
Compress-Archive -Path extension\* -DestinationPath frontend\extension.zip -Force
```

Or manually:
1. Navigate to the `extension` folder
2. Select all files (not the folder itself)
3. Right-click → Send to → Compressed (zipped) folder
4. Move `extension.zip` to the `frontend` folder

## 🔧 Local Testing

```powershell
# Serve locally with Python
cd frontend
python -m http.server 8000

# Or with Node.js
npx serve .

# Access at: http://localhost:8000
```

## 🎨 Customization

### Update Backend URL
Edit `script.js` line 2:
```javascript
const API_BASE = 'your-api-gateway-url';
```

### Modify Colors
Edit `styles.css` root variables:
```css
:root {
    --matrix-green: #00FF41;
    /* Add your custom colors */
}
```

### Add Screenshots
Replace the browser mock visual with actual screenshots:
1. Take a screenshot of the extension in action
2. Save as `extension-screenshot.png`
3. Update `index.html` to use `<img>` instead of the mock browser

## 📊 Features

- **Responsive Design**: Works on desktop, tablet, and mobile
- **Live Telemetry**: Real-time backend health checks every 30s
- **Interactive Elements**: Smooth scrolling, animations, copy-to-clipboard
- **Performance**: Optimized with Google Fonts preconnect
- **Accessibility**: Semantic HTML with proper ARIA labels

## 🌐 Production URL

Once deployed, update:
- `README.md` with the live URL
- Competition submission form
- Extension manifest's `homepage_url` field

## 📱 QR Code Generation

For the pitch presentation, generate a QR code:

```bash
# Using qrencode
qrencode -o landing-qr.png "https://your-deployed-url.com"

# Or use online tools:
# https://www.qr-code-generator.com/
```

## ✅ Pre-Launch Checklist

- [ ] Extension.zip file is in the frontend folder
- [ ] Backend API URL is correct in script.js
- [ ] Test all links (YouTube videos, API docs, health check)
- [ ] Verify mobile responsiveness
- [ ] Test extension download on different browsers
- [ ] Ensure HTTPS if using custom domain
- [ ] Add Google Analytics (optional)

## 🔍 Testing Checklist

- [ ] Hero section loads correctly
- [ ] Setup steps are clear and accurate
- [ ] Extension.zip downloads successfully
- [ ] Live telemetry updates every few seconds
- [ ] Backend health check works (green status)
- [ ] Architecture diagrams display properly
- [ ] All navigation links work
- [ ] YouTube test links open correctly
- [ ] Copy endpoint button works
- [ ] Footer links are functional

## 📈 Analytics (Optional)

Add Google Analytics for judge engagement tracking:

```html
<!-- Add before </head> in index.html -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

## 🎓 Judge Experience Flow

1. **Land on Hero** → Understand problem-solution in 10 seconds
2. **Setup Section** → Download extension and load in Chrome (60 seconds)
3. **Test Videos** → Visit educational YouTube and see it work (2-3 minutes)
4. **Telemetry** → See live system monitoring and AI activity
5. **Architecture** → Understand technical depth and innovation

## 🚨 Troubleshooting

**Extension won't load:**
- Ensure all files are extracted (not running from .zip)
- Check Developer Mode is enabled
- Verify manifest.json is valid

**Backend shows offline:**
- Check API Gateway is deployed
- Verify CORS settings allow requests
- Test `/health` endpoint directly

**Styling looks broken:**
- Ensure styles.css is in the same folder
- Check browser console for 404 errors
- Clear browser cache

## 📞 Support

For competition day support, ensure you can:
- Re-deploy quickly if needed
- Access AWS console from mobile
- Have backup URLs ready
- Monitor CloudWatch logs

---

**Built for AI for Bharat 2026** | Agentic Content Resiliency for Rural India
