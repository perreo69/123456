# ERP v135 — open-source visual system

- Inter: SIL Open Font License 1.1 — https://rsms.me/inter/ ; https://github.com/rsms/inter/blob/master/LICENSE.txt
- Pretendard v1.3.9: SIL Open Font License 1.1 — https://github.com/orioncactus/pretendard ; https://github.com/orioncactus/pretendard/blob/main/LICENSE
- Fonts loaded from upstream webfont services; no Apple font or SF Symbols file is bundled. Primary navigation, disclosure arrows, stock search and detail arrows in /erp/ use inline Lucide SVGs (ISC and applicable Feather MIT terms). Other existing inline vector icons are retained and styled with rounded strokes. See LUCIDE-LICENSE.txt for the upstream terms.
- HIG reference: https://developer.apple.com/design/human-interface-guidelines/ ; web dimensions are project choices, not exact native OS metrics.
- Primary routes: / and /erp/ (shell and embedded app); /erp/mobile-test.html is a separate test screen. Historical design previews are not updated.
- Changes are limited to stylesheets and font declarations; no Supabase, transaction, or event-handler logic changed. Screen-only shared CSS preserves print rules.
