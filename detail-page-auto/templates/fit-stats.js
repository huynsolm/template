document.fonts.ready.then(() => {
                    for (const value of document.querySelectorAll('.stat-list dd')) {
                        const initial = parseFloat(getComputedStyle(value).fontSize);
                        for (let size = initial; size >= 1; size -= 2) {
                            value.style.fontSize = size + 'px';
                            if (value.scrollWidth <= value.clientWidth) break;
                        }
                    }
                });
