# Image Optimization System

## Overview

This system automatically optimizes uploaded images (avatars and community covers) by creating two sizes for each upload:
- **Original/Full size**: Max 750px width, height auto-scaled, 85% quality JPEG
- **Thumbnail**: 200x200px square thumbnail, 85% quality JPEG

Old images are automatically deleted when new ones are uploaded to prevent storage waste.

## Features

### 1. **Automatic Image Optimization**
- Images are compressed to JPEG format with 85% quality
- Large images are resized to maximum 750px width
- Height automatically scales to maintain aspect ratio
- RGBA/PNG images are converted to RGB JPEG for better compression

### 2. **Thumbnail Generation**
- Automatic square thumbnails (200x200px)
- Center-cropped from original image
- Used for quick display in listings and previews

### 3. **Organized File Storage**
- Files are stored in structured folders:
  ```
  media/
  ├── profile-avatars/
  │   ├── {user_id}/
  │   │   ├── original/{filename}
  │   │   └── thumb_{filename}
  │
  ├── community_covers/
      ├── {community_id}/
          ├── original/{filename}
          └── thumb_{filename}
  ```

### 4. **Automatic Cleanup**
- When a user uploads a new avatar, the old avatar and thumbnail are deleted
- When a community uploads a new cover, the old cover and thumbnail are deleted
- No orphaned files remain in storage

## Implementation Details

### Files Created/Modified

1. **utils/image_utils.py** - Image processing utilities
   - `optimize_image()` - Resize and compress images
   - `create_thumbnail()` - Generate square thumbnails
   - `delete_image_file()` - Delete image files

2. **users/models.py** - Updated UserProfile model
   - Added `avatar_thumbnail` field
   - Added `avatar_upload_path()` function for organized storage
   - Added `avatar_thumbnail_upload_path()` function

3. **users/signals.py** - Signal handlers for UserProfile
   - `cleanup_avatar_on_update()` - Delete old images before saving new ones
   - `optimize_avatar()` - Optimize and create thumbnails after save

4. **pixelwar/models.py** - Updated Community model
   - Added `image_thumbnail` field
   - Added `community_image_upload_path()` function
   - Added `community_image_thumbnail_upload_path()` function

5. **pixelwar/signals.py** - NEW signal handlers for Community
   - `cleanup_community_image_on_update()` - Delete old images on update
   - `optimize_community_image()` - Optimize and create thumbnails

6. **pixelwar/apps.py** - Updated to register signals
   - Added `ready()` method to import signals

## How It Works

### When a user uploads a new avatar:

1. File is received by the upload handler
2. `pre_save` signal triggers:
   - If user has old avatar, it's deleted from storage
3. Image is saved to `profile-avatars/{user_id}/original/`
4. `post_save` signal triggers:
   - Image is optimized (resized if needed, compressed to JPEG)
   - Thumbnail is created (200x200px square crop)
   - Both files are saved without triggering signals again

### When a community uploads a new cover:

Same process as avatars, but for community covers in `community_covers/` folder.

## Usage in Templates

```html
<!-- Display optimized avatar -->
<img src="{{ user.profile.avatar.url }}" alt="User Avatar" class="avatar-full">

<!-- Display thumbnail (faster loading) -->
<img src="{{ user.profile.avatar_thumbnail.url }}" alt="User Avatar" class="avatar-thumb">

<!-- Display community cover -->
<img src="{{ community.image.url }}" alt="Community Cover" class="cover-full">

<!-- Display community thumbnail -->
<img src="{{ community.image_thumbnail.url }}" alt="Community Cover" class="cover-thumb">
```

## Configuration Options

In `utils/image_utils.py`, you can adjust:

- **max_width**: Maximum width for full images (default: 750px)
- **thumbnail_size**: Thumbnail dimensions (default: 200x200px)
- **quality**: JPEG quality (default: 85, range 1-100)

## Benefits

✅ **Storage Optimization**: Compressed JPEG format saves 60-80% vs PNG
✅ **Faster Loading**: Thumbnails for quick page loads
✅ **Clean Storage**: Old files automatically deleted
✅ **Organized Structure**: Files organized by user/community ID
✅ **Automatic Processing**: No manual intervention needed
✅ **Better Performance**: Properly sized images reduce bandwidth

## Future Enhancements

- [ ] WebP format support for modern browsers
- [ ] Progressive image loading with blur-up effect
- [ ] CDN integration for image serving
- [ ] Image cropping/editing UI
- [ ] Batch optimization for existing images
