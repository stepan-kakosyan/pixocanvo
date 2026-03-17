(() => {
    function byId(id) {
        return document.getElementById(id);
    }

    function show(el) {
        if (el) {
            el.classList.remove('hidden');
        }
    }

    function hide(el) {
        if (el) {
            el.classList.add('hidden');
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        const modalBackdrop = byId('modal-backdrop');
        const invitationModal = byId('invitation-modal');
        const leaveModal = byId('leave-modal');
        const deleteModal = byId('delete-modal');

        const invitationInput = byId('invitation-link-input');
        const copyInviteButton = byId('copy-invite-link-btn');

        const leaveForm = byId('leave-community-form');
        const deleteForm = byId('delete-community-form');
        const leaveModalText = byId('leave-modal-text');
        const deleteModalText = byId('delete-modal-text');

        if (!modalBackdrop) {
            return;
        }

        const hideAllModals = () => {
            hide(modalBackdrop);
            hide(invitationModal);
            hide(leaveModal);
            hide(deleteModal);
        };

        const openModal = (modal) => {
            if (!modal) {
                return;
            }
            show(modalBackdrop);
            show(modal);
        };

        document.querySelectorAll('.invitation-link-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                const url = String(btn.getAttribute('data-invite-url') || '');
                if (invitationInput) {
                    invitationInput.value = url;
                }
                openModal(invitationModal);
            });
        });

        if (copyInviteButton && invitationInput) {
            copyInviteButton.addEventListener('click', async () => {
                const url = invitationInput.value;
                try {
                    if (navigator.clipboard && navigator.clipboard.writeText) {
                        await navigator.clipboard.writeText(url);
                    } else {
                        invitationInput.focus();
                        invitationInput.select();
                        document.execCommand('copy');
                    }
                    copyInviteButton.textContent = 'Copied!';
                    window.setTimeout(() => {
                        copyInviteButton.textContent = 'Copy URL';
                    }, 1200);
                } catch (_error) {
                    copyInviteButton.textContent = 'Copy failed';
                    window.setTimeout(() => {
                        copyInviteButton.textContent = 'Copy URL';
                    }, 1200);
                }
            });
        }

        document.querySelectorAll('.leave-community-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                const slug = String(btn.getAttribute('data-community-slug') || '');
                const name = String(btn.getAttribute('data-community-name') || '');
                const leaveUrl = String(btn.getAttribute('data-leave-url') || '');
                if (leaveForm) {
                    leaveForm.action = leaveUrl;
                }
                if (leaveModalText && name) {
                    leaveModalText.textContent = `Are you sure you want to leave "${name}"?`;
                }
                openModal(leaveModal);
            });
        });

        document.querySelectorAll('.delete-community-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                const slug = String(btn.getAttribute('data-community-slug') || '');
                const name = String(btn.getAttribute('data-community-name') || '');
                const deleteUrl = String(btn.getAttribute('data-delete-url') || '');
                if (deleteForm) {
                    deleteForm.action = deleteUrl;
                }
                if (deleteModalText && name) {
                    deleteModalText.textContent = `Delete "${name}" permanently? This action cannot be undone. All data will be deleted and cannot be restored.`;
                }
                openModal(deleteModal);
            });
        });

        document.querySelectorAll('.close-modal-btn').forEach((btn) => {
            btn.addEventListener('click', hideAllModals);
        });

        modalBackdrop.addEventListener('click', hideAllModals);

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                hideAllModals();
            }
        });
    });
})();
