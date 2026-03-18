from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import UserProfile


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    avatar = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2", "avatar")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].strip().lower()
        if commit:
            user.save()
            avatar = self.cleaned_data.get("avatar")
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if avatar:
                profile.avatar = avatar
                profile.save(update_fields=["avatar"])
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(max_length=150, label="Username or email")

    def clean(self):
        identifier = str(self.cleaned_data.get("username", "")).strip()
        if "@" in identifier:
            user = User.objects.filter(email__iexact=identifier).first()
            if user is not None:
                self.cleaned_data["username"] = user.username
        return super().clean()


class ForgotPasswordForm(forms.Form):
    identifier = forms.CharField(max_length=254, label="Username or email")


class ProfileSettingsForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=True)
    avatar = forms.ImageField(required=False)
    new_password1 = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        label="New password",
    )
    new_password2 = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        label="Confirm new password",
    )

    def __init__(self, *args, user: User, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

        if not self.is_bound:
            self.initial["username"] = user.username
            self.initial["email"] = user.email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        qs = User.objects.filter(username__iexact=username).exclude(pk=self.user.pk)
        if qs.exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        qs = User.objects.filter(email__iexact=email).exclude(pk=self.user.pk)
        if qs.exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def clean(self):
        cleaned = super().clean()
        password_1 = cleaned.get("new_password1", "")
        password_2 = cleaned.get("new_password2", "")

        if password_1 or password_2:
            if password_1 != password_2:
                raise forms.ValidationError("New password fields must match.")
            if len(password_1) < 8:
                raise forms.ValidationError("New password must be at least 8 characters.")

        return cleaned

    def save(self):
        self.user.username = self.cleaned_data["username"]
        self.user.email = self.cleaned_data["email"]
        self.user.save(update_fields=["username", "email"])

        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        avatar = self.cleaned_data.get("avatar")
        if avatar:
            profile.avatar = avatar
            profile.save(update_fields=["avatar"])

        new_password = self.cleaned_data.get("new_password1", "")
        if new_password:
            self.user.set_password(new_password)
            self.user.save(update_fields=["password"])

        return self.user
