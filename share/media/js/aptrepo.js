
/*
 * Downloads a package based on attributes specified in the element
 */
function download_package(ev) {
	
	// retrieve the URL of the package by making an Ajax API call on its metadata
	var package_metadata_url = '/aptrepo/api/packages/deb822/' + 
		$(this).attr('package_name') + '/' +
		$(this).attr('version') + '/' +
		$(this).attr('architecture');
	ev.preventDefault();
	$.getJSON( package_metadata_url, function(package_metadata) {
		// download the package based on the path
		window.location.href = '/aptrepo/public/' + package_metadata['path'];
	})
	.error( function() {
		alert( gettext('Package no longer exists.') );
	});
}
