(() => {
  const header = document.querySelector('.site-header');
  const progress = document.querySelector('.progress');
  const copyStatus = document.getElementById('copy-status');
  const lightbox = document.getElementById('lightbox');
  const lightboxImage = lightbox?.querySelector('img');
  const lightboxClose = lightbox?.querySelector('.lightbox__close');
  let lastFocused = null;

  const copyText = async (text) => {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch {
      }
    }
    const field = document.createElement('textarea');
    field.value = text;
    field.setAttribute('readonly', '');
    field.style.position = 'fixed';
    field.style.opacity = '0';
    document.body.append(field);
    field.select();
    const copied = document.execCommand('copy');
    field.remove();
    if (!copied) {
      throw new Error('Copy failed');
    }
    return true;
  };

  const markCopied = (button) => {
    const label = button.querySelector('span');
    if (label) {
      if (!button.dataset.originalLabel) {
        button.dataset.originalLabel = label.textContent;
      }
      label.textContent = 'Copied';
    }
    button.classList.add('is-copied');
    if (copyStatus) {
      copyStatus.textContent = 'Copied to clipboard';
    }
    window.clearTimeout(button.copyTimer);
    button.copyTimer = window.setTimeout(() => {
      button.classList.remove('is-copied');
      if (label && button.dataset.originalLabel) {
        label.textContent = button.dataset.originalLabel;
      }
    }, 1600);
  };

  document.querySelectorAll('[data-copy]').forEach((button) => {
    button.addEventListener('click', async () => {
      try {
        const copied = await copyText(button.dataset.copy);
        if (copied) {
          markCopied(button);
        }
      } catch {
        if (copyStatus) {
          copyStatus.textContent = 'Copy failed';
        }
      }
    });
  });

  const closeLightbox = () => {
    if (!lightbox || lightbox.hidden) {
      return;
    }
    lightbox.hidden = true;
    lightboxImage.removeAttribute('src');
    lightboxImage.alt = '';
    document.body.classList.remove('lightbox-open');
    lastFocused?.focus();
  };

  const openLightbox = (link) => {
    if (!lightbox || !lightboxImage) {
      return;
    }
    lastFocused = document.activeElement;
    lightboxImage.src = link.href;
    lightboxImage.alt = link.dataset.lightboxAlt || link.querySelector('img')?.alt || '';
    lightbox.hidden = false;
    document.body.classList.add('lightbox-open');
    lightboxClose?.focus();
  };

  document.querySelectorAll('[data-lightbox]').forEach((link) => {
    link.addEventListener('click', (event) => {
      event.preventDefault();
      openLightbox(link);
    });
  });

  lightbox?.addEventListener('click', (event) => {
    if (event.target === lightbox) {
      closeLightbox();
    }
  });

  lightboxClose?.addEventListener('click', closeLightbox);

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && menu?.open) {
      menu.open = false;
    }
    if (lightbox?.hidden) {
      return;
    }
    if (event.key === 'Escape') {
      closeLightbox();
    }
    if (event.key === 'Tab') {
      event.preventDefault();
      lightboxClose?.focus();
    }
  });

  const menu = document.querySelector('.menu');
  menu?.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => menu.removeAttribute('open'));
  });
  document.addEventListener('click', (event) => {
    if (menu?.open && !menu.contains(event.target)) {
      menu.open = false;
    }
  });

  const revealItems = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -7% 0px', threshold: 0.08 });
    revealItems.forEach((item) => observer.observe(item));
  } else {
    revealItems.forEach((item) => item.classList.add('is-visible'));
  }

  let scrollScheduled = false;
  const updateScroll = () => {
    const scrollTop = window.scrollY;
    const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
    if (progress) {
      progress.style.width = `${maxScroll > 0 ? Math.min(100, (scrollTop / maxScroll) * 100) : 0}%`;
    }
    header?.classList.toggle('is-scrolled', scrollTop > 12);
    scrollScheduled = false;
  };

  window.addEventListener('scroll', () => {
    if (!scrollScheduled) {
      scrollScheduled = true;
      window.requestAnimationFrame(updateScroll);
    }
  }, { passive: true });

  updateScroll();
})();
