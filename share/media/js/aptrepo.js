/*globals $, jQuery, sprintf, gettext */

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
 * Construct a REST API URL for a specific distribution
 */
function get_distribution_url( distribution_name ) {
	return '/aptrepo/web/distributions/' + distribution_name + '/';
}


/*
 * Common callback for anchor elements with package metadata attributes
 */
function on_click_package_anchor(ev) {
	ev.preventDefault();
	
	// retrieve the URL of the package by making an Ajax API call on its metadata
	var section_name = $(this).attr('target_section_name'),
		section_id = $(this).attr('target_section_id'),
		aux_flags = {},
		instance_metadata_url = get_instance_url(
			section_id, 
			$(this).attr('package_name'),
			$(this).attr('version'),
			$(this).attr('architecture')
		);
	
	if ( ev.data.hasOwnProperty('aux_flags') ) {
		aux_flags = ev.data.aux_flags; 
	}
	
	$.getJSON( instance_metadata_url)
	.success( function( instance_metadata ) {
		ev.data.package_callback(
			ev, 
			instance_metadata, 
			section_name,
			section_id,
			aux_flags
		);
	})
	.error( function() {
		alert( gettext('Package instance no longer exists.') );
	});
}

/*
 * Downloads the package based on the path in the metadata 
 */
function download_package_for_instance( instance_metadata ) {
	window.location.href = '/aptrepo/repository/' + instance_metadata['package']['path'];
}

/*
 * Wrapper callback for a package's download link
 */
function download_package_callback(ev, instance_metadata, section_name, section_id, aux_flags) {
	download_package_for_instance( instance_metadata );
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
function populate_package_info_dialog( instance_metadata, section_name, aux_flags )
{
	// set the dialog title
	var package_info_dialog = $('div#package_info_dialog'),
		package_path = instance_metadata['package']['path'],
		filename = package_path.substr(package_path.lastIndexOf('/') + 1),
		enable_delete_button = true,
		enable_copy_button = true,
		PACKAGE_MISC_INFO_ROWS = {
			creator : 1,
			creation_date : 2,
			size : 3,
			md5 : 4,
			sha1 : 5,
			sha256 : 6
		};		

	package_info_dialog.dialog( 
		{title: gettext('%s in %s').printf(filename, section_name) } 
	);
	
	// populate the Debian control info
	package_info_dialog.find('pre#package_info_dialog_control_data').html(
		instance_metadata['package']['control']
	);
	
	// populate the miscellaneous info
	var misc_info_table = package_info_dialog.find('table#package_info_dialog_misc_data'),
		fn_set_table_entry = function( row_id, value ) {
			misc_info_table.find(
				'tr:nth-child(%d) :nth-child(2)'.printf( row_id )
			).html( value );
		};
	fn_set_table_entry( PACKAGE_MISC_INFO_ROWS.creator, instance_metadata['creator'] );
	fn_set_table_entry( PACKAGE_MISC_INFO_ROWS.creation_date, instance_metadata['creation_date'] );
	fn_set_table_entry( PACKAGE_MISC_INFO_ROWS.size, instance_metadata['package']['size'] );
	fn_set_table_entry( PACKAGE_MISC_INFO_ROWS.md5, instance_metadata['package']['hash_md5'] );
	fn_set_table_entry( PACKAGE_MISC_INFO_ROWS.sha1, instance_metadata['package']['hash_sha1'] );
	fn_set_table_entry( PACKAGE_MISC_INFO_ROWS.sha256, instance_metadata['package']['hash_sha256'] );
	
	// setup the buttons
	if (aux_flags.hasOwnProperty('enable_delete_button')) {
		enable_delete_button = aux_flags.enable_delete_button;
	}
	if (aux_flags.hasOwnProperty('enable_copy_button')) {
		enable_copy_button = aux_flags.enable_copy_button;
	}
	
	$('#package_info_dialog_buttons button#download').off('click').click( function() {
		download_package_for_instance( instance_metadata );
	});
	if (enable_copy_button) {
		$('#package_info_dialog_buttons button#copy').off('click').click( function() {
			window.location.href = '/aptrepo/web/packages/copy/?instance=' + 
				instance_metadata['id'] + '&next=' + window.location.href;
		});
	}
	else {
		$('#package_info_dialog_buttons button#copy').hide();
	}
	
	if (enable_delete_button) {
		setup_delete_button( $('#package_info_dialog_buttons button#delete'), instance_metadata );
	}
	else {
		$('#package_info_dialog_buttons button#delete').hide();
	}
}

/*
 * Shows a modal dialog of the package metadata
 */
function show_package_info_dialog(ev, instance_metadata, section_name, section_id, aux_flags) {
	
	// setup the package info dialog
	var package_info_dialog = $('div#package_info_dialog'),
		instance_url_for_architectures = get_instance_url(
			section_id,
			instance_metadata['package']['package_name'],
			instance_metadata['package']['version']
		);	
	package_info_dialog.dialog({
		autoOpen: false,
		modal: true,
		minWidth: package_info_dialog.width()
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
	$.getJSON( instance_url_for_architectures )
	.success( function( all_archs_data ) {

		var idx,
			architecture_dropdown = $('#package_info_architectures_dropdown');
		
		architecture_dropdown.html('');
		for (idx = 0; idx < all_archs_data.length; ++idx) {
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
				populate_package_info_dialog( new_instance_metadata, section_name, aux_flags );
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
		populate_package_info_dialog( instance_metadata, section_name, aux_flags );
		package_info_dialog.dialog("open");
	});

	return false;
}


/*
 * Initializes the tree control for browsing the repository distributions
 */
function initialize_distributions_treecontrol( elem_distributions_container ) {
	
	// setup tree control
	// TODO Customize theme graphics and generate them from SVG
	// TODO Avoid using absolute URL when specifying theme directory
	elem_distributions_container
		.bind('select_node.jstree', function( ev, data ) {
			var href = data.rslt.obj.children("a").attr("href");
			if (href && href !== '#') {
				document.location.href = href;
			}
		})
		.jstree({
			plugins : [ "themes", "html_data", "ui"],
			"core" : {
				"initially_open": ["distribution_root"]
			},
			"themes" : {
				"theme": "default",
				"url": "/aptrepo/media/css/repository_tree/style.css",
				"dots": true,
				"icons": true
			},
			"ui" : {
				"select_limit" : 2,
				"initially_select" : ["distribution_root"]
			}
	});

	// erase info window if clicking on the root distribution node
	var info_table = $('#distributions_section_info_table>tbody');
	elem_distributions_container.on('click', 'li#distribution_root>a', function() {
		info_table.html('');
	});
	
	// setup callback for clicking on a distribution
	var append_data_to_table = function(data_dict) {
		var i;
		for (i in data_dict) {
			if ( data_dict.hasOwnProperty(i) ) {
				info_table.append( $('<tr>')
					.append( 
						$('<td>').text(data_dict[i][0])
						.after( $('<td>').text(data_dict[i][1]) )
					)
				);
			}
		}
	};
	elem_distributions_container.on('click', 'a[distribution_name]', function() {
		
		// query and populate information on the distribution
		var distribution_name = $(this).attr('distribution_name');
		info_table.html('');

		$.getJSON( get_distribution_url(distribution_name) )
		.success( function( distribution_data ) {
			append_data_to_table( distribution_data );
		})
		.error( function() {
			alert( gettext('Unable to retrieve distribution information') );
		});
	});
}
