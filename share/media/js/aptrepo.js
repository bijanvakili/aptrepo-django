/*
 * Common callback for anchor elements with package metadata attributes
 */
function on_click_package_anchor(ev) {
	ev.preventDefault();
	
	// retrieve the URL of the package by making an Ajax API call on its metadata
	var section_name = $(this).attr('target_section_name'); 
	var instance_metadata_url = '/aptrepo/api/sections/' +
		$(this).attr('target_section_id') + '/package-instances/deb822/' + 
		$(this).attr('package_name') + '/' +
		$(this).attr('version') + '/' +
		$(this).attr('architecture');
	$.getJSON( instance_metadata_url, function(instance_metadata) {
		ev.data.package_callback(
			ev, 
			instance_metadata, 
			section_name
		);
	})
	.error( function() {
		alert( gettext('Package no longer exists.') );
	});
}

/*
 * Downloads the package based on the path in the metadata 
 */
function download_package(ev, instance_metadata, section_name) {
	window.location.href = '/aptrepo/public/' + instance_metadata['package']['path'];
}

/*
 * Shows a modal dialog of the package metadata
 */
function show_package_info_dialog(ev, instance_metadata, section_name) {
	
	/* TODO Remaining items for package information dialog
	 * - Add miscellaneous metadata (uploader, file size, etc.)
	 * - Alternate the color of the rows for the 'control' information
	 * - Add buttons for download, copy and delete
	 * - Add radio control to select between architectures
	 * - Consider generating all jQuery UI images from .svgs
	 */
	var package_path = instance_metadata['package']['path'];
	var filename = package_path.substr(package_path.lastIndexOf('/') + 1) 
	var dialog = $('<div></div>')
		.html('<pre>' + instance_metadata['package']['control'] + '</pre>')
		.dialog({
			autoOpen: false,
			modal: true,
			overlay: { opacity: 0.5, background: 'black'},
			title: gettext('%s in %s').printf(filename, section_name),
			minWidth: 500,
			buttons: {
				"Close": function() {
					$(this).dialog("close");
				},
			}
		});
	dialog.dialog("open");
	return false;
}
