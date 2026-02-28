# Placeholder Icons
# For Phase 1, these are simple SVG placeholders
# Replace with actual icon images in production

# Icon format: PNG files at 16x16, 32x32, 48x48, and 128x128 pixels
# Colors: Using Sanchar-Optimize brand gradient (#667eea to #764ba2)

# To create actual icons:
# 1. Use a tool like Figma, Canva, or Inkscape
# 2. Export as PNG at the required sizes
# 3. Place in this directory with the correct filenames:
#    - icon-16.png
#    - icon-32.png
#    - icon-48.png
#    - icon-128.png

# For now, you can create simple placeholder PNGs or use the SVG template below
# and convert it to PNG using an online tool like cloudconvert.com

SVG_TEMPLATE = '''
<svg width="128" height="128" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#667eea;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#764ba2;stop-opacity:1" />
    </linearGradient>
  </defs>
  
  <!-- Background circle -->
  <circle cx="64" cy="64" r="60" fill="url(#grad)" />
  
  <!-- Shield shape (simplified) -->
  <path d="M 64 20 L 90 35 L 90 70 Q 90 90 64 105 Q 38 90 38 70 L 38 35 Z" 
        fill="white" opacity="0.9" />
  
  <!-- Signal waves -->
  <path d="M 64 55 Q 70 55 70 62 Q 70 69 64 69 Q 58 69 58 62 Q 58 55 64 55" 
        fill="#667eea" />
  <path d="M 54 45 Q 48 48 48 55" stroke="#667eea" stroke-width="3" 
        fill="none" opacity="0.6" />
  <path d="M 74 45 Q 80 48 80 55" stroke="#667eea" stroke-width="3" 
        fill="none" opacity="0.6" />
</svg>
'''

# Save this SVG and convert to PNG at required sizes
print("Icon template created. Convert to PNG using:")
print("1. Save the SVG template above to a file")
print("2. Use https://cloudconvert.com/svg-to-png")
print("3. Export at 16px, 32px, 48px, and 128px")
print("4. Place the PNG files in this directory")
