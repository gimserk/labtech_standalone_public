/* Client-side discovery only. No data requests, no changes to permissions or records. */
document.addEventListener('DOMContentLoaded', () => {
    const toolSearch = document.querySelector('[data-workspace-tool-search]');
    if (toolSearch) {
        const sections = Array.from(document.querySelectorAll('[data-workspace-tool-group]'));
        const links = Array.from(document.querySelectorAll('[data-workspace-tool]'));
        const result = document.querySelector('[data-workspace-tool-result]');
        const empty = document.querySelector('[data-workspace-tool-empty]');

        const filterTools = () => {
            const needle = toolSearch.value.trim().toLocaleLowerCase();
            let count = 0;
            sections.forEach(section => {
                let groupCount = 0;
                section.querySelectorAll('[data-workspace-tool]').forEach(link => {
                    const visible = !needle || link.textContent.toLocaleLowerCase().includes(needle);
                    link.closest('li').hidden = !visible;
                    if (visible) groupCount++;
                });
                section.hidden = groupCount === 0;
                count += groupCount;
            });
            if (result) result.textContent = needle
                ? count + ' of ' + links.length + ' tools match'
                : links.length + ' tools available';
            if (empty) empty.hidden = count !== 0;
        };
        toolSearch.addEventListener('input', filterTools);
        filterTools();
    }

    const courseSearch = document.querySelector('[data-course-index-search]');
    const courseStatus = document.querySelector('[data-course-index-status]');
    if (courseSearch && courseStatus) {
        const rows = Array.from(document.querySelectorAll('[data-course-row]'));
        const result = document.querySelector('[data-course-filter-summary]');
        const empty = document.querySelector('[data-course-filter-empty]');
        const archived = document.getElementById('collapseArchived');

        const filterCourses = () => {
            const needle = courseSearch.value.trim().toLocaleLowerCase();
            const wantedStatus = courseStatus.value;
            let count = 0;
            let archivedVisible = false;
            rows.forEach(row => {
                const status = row.dataset.courseStatus;
                const visible = (!needle || row.textContent.toLocaleLowerCase().includes(needle))
                    && (wantedStatus === 'all' || status === wantedStatus);
                row.hidden = !visible;
                if (visible) count++;
                if (visible && status === 'archived') archivedVisible = true;
            });
            if (result) result.textContent = count + ' of ' + rows.length + ' courses match';
            if (empty) empty.hidden = count !== 0;
            // Reveal archived results when someone searches for them; never close a user-opened list.
            if (archivedVisible && archived && (needle || wantedStatus === 'archived') && window.bootstrap?.Collapse) {
                window.bootstrap.Collapse.getOrCreateInstance(archived, {toggle: false}).show();
            }
        };
        courseSearch.addEventListener('input', filterCourses);
        courseStatus.addEventListener('change', filterCourses);
        filterCourses();

        // Dashboard links may target the archived list or a specific archived row.
        if (archived && window.bootstrap?.Collapse) {
            const targetId = window.location.hash.slice(1);
            const target = targetId && document.getElementById(targetId);
            if (targetId === 'archivedCoursesAccordion' || target === archived
                || (target && archived.contains(target))) {
                window.bootstrap.Collapse.getOrCreateInstance(archived, {toggle: false}).show();
            }
        }
    }
});
