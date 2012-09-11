/*
 * Construct a REST API URL for a specific package instance
 */
function get_instance_url( 
	target_section_id, 
	package_name, 
	version, 
	architecture 
) 
{
	var url = sprintf(
		'/aptrepo/api/sections/%s/package-instances/deb822/%s/%s/',
		target_section_id,
		package_name,
		version
	);
	if ( architecture ) {
		url += architecture + '/';
	}
	
	return url;
}


/*
 * Common callback for anchor elements with package metadata attributes
 */
function on_click_package_anchor(ev) {
	ev.preventDefault();
	
	// retrieve the URL of the package by making an Ajax API call on its metadata
	var section_name = $(this).attr('target_section_name');
	var section_id = $(this).attr('target_section_id');
	var instance_metadata_url =  get_instance_url(
		section_id, 
		$(this).attr('package_name'),
		$(this).attr('version'),
		$(this).attr('architecture')
	);
	$.getJSON( instance_metadata_url)
	.success( function( instance_metadata ) {
		ev.data.package_callback(
			ev, 
			instance_metadata, 
			section_name,
			section_id
		);
	})
	.error( function() {
		alert( gettext('Package instance no longer exists.') );
	});
}

/*
 * Wrapper callback for a package's download link
 */
function download_package_callback(ev, instance_metadata, section_name, section_id) {
	download_package_for_instance( instance_metadata );
}

/*
 * Downloads the package based on the path in the metadata 
 */
function download_package_for_instance( instance_metadata ) {
	window.location.href = '/aptrepo/public/' + instance_metadata['package']['path'];
}


function setup_download_button( button, instance_metadata ) {
	button.off('click').click( function() {
		download_package_for_instance( instance_metadata );
	});
}

function setup_delete_button( button, instance_metadata ) {
	button.off('click').click( function() {
		if ( confirm(gettext('Are you sure you want to delete the package?')) ) {
			// delete a package instance
			$.ajax( {
				url: '/aptrepo/api/package-instances/' + instance_metadata['id'] + '/',
				type: 'DELETE'
			}).success( function() {
				alert( gettext('Package instance succsessfully deleted.'));
				$('div#package_info_dialog').dialog("close");
			}).error( function() {
				alert( gettext('Unable to delete package instance.'));
			});
		}
	});
}


/*
 * Populates the package info dialog with the metadata from a package instance
 */
function populate_package_info_dialog( instance_metadata, section_name )
{
	var package_info_dialog = $('div#package_info_dialog');
	
	// set the dialog title
	var package_path = instance_metadata['package']['path'];
	var filename = package_path.substr(package_path.lastIndexOf('/') + 1);
	package_info_dialog.dialog( 
		{title: gettext('%s in %s').printf(filename, section_name) } 
	);
	
	// populate the Debian control info
	package_info_dialog.find('pre#package_info_dialog_control_data').html(
		instance_metadata['package']['control']
	);
	
	// populate the miscellaneous info
	var misc_info_table = package_info_dialog.find('table#package_info_dialog_misc_data');
	var fn_set_table_entry = function( row_id, value ) {
		misc_info_table.find(
			'tr:nth-child(%d) :nth-child(2)'.printf( row_id )
		).html( value );
	};
	var PACKAGE_MISC_INFO_ROWS = {
		creator : 1,
		creation_date : 2,
		size : 3,
		md5 : 4,
		sha1 : 5,
		sha256 : 6
	};
	fn_set_table_entry( PACKAGE_MISC_INFO_ROWS.creator, instance_metadata['creator'] );
	fn_set_table_entry( PACKAGE_MISC_INFO_ROWS.creation_date, instance_metadata['creation_date'] );
	fn_set_table_entry( PACKAGE_MISC_INFO_ROWS.size, instance_metadata['package']['size'] );
	fn_set_table_entry( PACKAGE_MISC_INFO_ROWS.md5, instance_metadata['package']['hash_md5'] );
	fn_set_table_entry( PACKAGE_MISC_INFO_ROWS.sha1, instance_metadata['package']['hash_sha1'] );
	fn_set_table_entry( PACKAGE_MISC_INFO_ROWS.sha256, instance_metadata['package']['hash_sha256'] );
	
	// update the button links
	setup_download_button( $('#package_info_dialog_buttons button#download'), instance_metadata );
	setup_delete_button( $('#package_info_dialog_buttons button#delete'), instance_metadata );
	// TODO implement copy button
}

/*
 * Shows a modal dialog of the package metadata
 */
function show_package_info_dialog(ev, instance_metadata, section_name, section_id) {
	
	// setup the package info dialog
	var package_info_dialog = $('div#package_info_dialog');
	package_info_dialog.dialog({
		autoOpen: false,
		modal: true,
		minWidth: package_info_dialog.width(),
	});
	$('#package_info_dialog_buttons button#download').button({
		icons : {primary: 'ui-icon-arrowthick-1-s'}
	});
	$('#package_info_dialog_buttons button#copy').button({
		icons : {primary: 'ui-icon-copy'}
	});
	$('#package_info_dialog_buttons button#delete').button({
		icons : {primary: 'ui-icon-trash'}
	});
	
	$('#package_info_dialog_buttons button#close').button({
		icons : {primary: 'ui-icon-close'}
	}).click( function() { 
		package_info_dialog.dialog("close"); 
	});
	
	// retrieve and add a radio button for all architecture choices
	var instance_url_for_architectures = get_instance_url(
		section_id,
		instance_metadata['package']['package_name'],
		instance_metadata['package']['version']
	);
	$.getJSON( instance_url_for_architectures )
	.success( function( all_archs_data ) {
		var architecture_dropdown = $('#package_info_architectures_dropdown');
		architecture_dropdown.html('');

		for (var idx in all_archs_data) {
			architecture_dropdown.append( 
				$('<option/>')
				.val(all_archs_data[idx]['package']['architecture'])
				.text(all_archs_data[idx]['package']['architecture'])
			);
		}
		architecture_dropdown.val( 
			instance_metadata['package']['architecture']
		);

		// add ability to switch between architectures
		architecture_dropdown.off('change');
		architecture_dropdown.change( function(change_event) {
			var new_instance_url = get_instance_url(
				section_id,
				instance_metadata['package']['package_name'],
				instance_metadata['package']['version'],
				architecture_dropdown.val()
			);
			$.getJSON( new_instance_url )
			.success( function( new_instance_metadata ) {
				populate_package_info_dialog( new_instance_metadata, section_name );
			})
			.error( function() {
				alert( gettext('Unable to retrieve package instance metadata.') );
			});
		}); 
	})
	.error( function() {
		alert( gettext('Unable to retrieve architecture list.') );
	})
	.then( function() {
		// initialize the rest of the dialog and open it 
		populate_package_info_dialog( instance_metadata, section_name );
		package_info_dialog.dialog("open");
	});

	return false;
}
