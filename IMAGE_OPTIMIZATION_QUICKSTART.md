# Image Optimization - Quick Start Guide

## 🚀 What's New

Your Django project now has automatic image optimization for:
- **User Avatars** - stored in `profile-avatars/`
- **Community Covers** - stored in `community_covers/`

## ✨ Key Features

✅ **Automatic Resizing** - Images max 750px width (height auto-scales)
✅ **Thumbnail Generation** - 200x200px square thumbnails for fast loading
✅ **Compression** - JPEG format saves 60-80% storage vs PNG
✅ **Auto Cleanup** - Old images deleted when new ones uploaded
✅ **Organized Storage** - Files stored by user/community ID

## 📁 File Structure

```
media/
├── profile-avatars/
│   └── {user_id}/
│       ├── original/avatar.jpg (750px max width)
│       └── thumb_avatar.jpg (200x200px)
│
└── community_covers/
    └── {community_id}/
        ├── original/cover.jpg (750px max width)
        └── thumb_cover.jpg (200x200px)
```

## 🏗️ Implementation Files

### Core Utility
- **utils/image_utils.py** - Image processing functions

### User Avatars  
- **users/models.py** - Added `avatar_thumbnail` field
- **users/signals.py** - Auto-optimization & cleanup on save

### Community Covers
- **pixelwar/models.py** - Added `image_thumbnail` field  
- **pixelwar/signals.py** - Auto-optimization & cleanup on save
- **pixelwar/apps.py** - Signals registration

### Database
- **users/migrations/0002_userprofile_avatar_thumbnail.py**
- **pixelwar/migrations/0009_community_image_thumbnail.py**

## 💻 Usage Example

### In Templates

```html
<!-- Display user avatar -->
<!-- Full size (750px max): -->
<img src="{{ user.profile.avatar.url }}" alt="Avatar" class="avatar-lg">

<!-- Thumbnail (200x200): -->
<img src="{{ user.profile.avatar_thumbnail.url }}" alt="Avatar" class="avatar-sm">

<!-- Display community cover -->
<!-- Full size (750px max): -->
<img src="{{ community.image.url }}" alt="Cover" class="cover-lg">

<!-- Thumbnail (200x200): -->
<img src="{{ community.image_thumbnail.url }}" alt="Cover" class="cover-sm">
```

### In Views

```python
def upload_avatar(request):
    profile = request.user.profile
    profile.avatar = request.FILES['avatar']
    profile.save()  # Signals handle optimization automatically
    
    # Access the images:
    full_url = profile.avatar.url  # Original optimized image
    thumb_url = profile.avatar_thumbnail.url  # Thumbnail
```

## 🔧 Configuration

Edit `utils/image_utils.py` to customize:

```python
def optimize_image(image_file, max_width=750, quality=85):
    # max_width: Maximum pixel width (750)
    # quality: JPEG quality 1-100 (85)

def create_thumbnail(image_file, size=200, quality=85):
    # size: Thumbnail square size in pixels (200)
    # quality: JPEG quality 1-100 (85)
```

## 🚀 Next Steps

1. **Run Migrations**
   ```bash
   python manage.py migrate users pixelwar
   ```

2. **Test Upload**
   - Create/edit a user profile with avatar
   - Create/edit a community with cover image
   - Check `media/` folder structure

3. **Update Forms** (if using custom forms)
   ```python
   class AvatarForm(forms.ModelForm):
       class Meta:
           model = UserProfile
           fields = ['avatar']
           # thumbnail auto-generated on save
   ```

## 📊 Storage Savings Example

**Before optimization:**
- PNG avatar: 500 KB
- PNG thumbnail: 200 KB
- Total: 700 KB

**After optimization:**
- JPEG optimized: 100 KB
- JPEG thumbnail: 40 KB  
- Total: 140 KB
- **Saving: 80%** 🎉

## ⚠️ Important Notes

- Images are **automatically processed** - no additional code needed
- Old images are **automatically deleted** - no storage waste
- **Thumbnail field is optional** - will be created automatically
- **Supports all image formats** - PNG, JPG, GIF, BMP, etc.
- Converted to optimized **JPEG format** for best compression

## 🐛 Troubleshooting

**Images not optimizing?**
- Check that `Pillow` is installed: `pip install Pillow`
- Verify signals are imported (check app config `ready()` method)
- Check database migrations ran: `python manage.py migrate`

**Old images still in folder?**
- May be old uploads before feature implementation
- Safe to manually delete `media/profile-avatars/` and `media/community_covers/`
- New uploads will use new structure

**Thumbnail not created?**
- Check for errors in Django logs
- Verify `avatar` field has an image value
- Try re-uploading the image

---

📖 See [IMAGE_OPTIMIZATION.md](./IMAGE_OPTIMIZATION.md) for detailed technical documentation.
