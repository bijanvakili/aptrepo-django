/*globals $, jQuery */
/*
 * Initializes an advanced file input widget
 */
function initialize_advanced_fileinput(elem_fileinput_container) {
	var hidden_file_input = elem_fileinput_container.find('input[type="file"]'),
		visible_filepath_text_control = elem_fileinput_container.find('input[type="text"]'),
		visible_choosefile_button = elem_fileinput_container.find('input[type="button"]'),
		initial_path_text = visible_filepath_text_control.val();

	// reroute visible button clicks to hidden file control click callback
	visible_choosefile_button.click( function() {
		hidden_file_input.click();
	});
	
	// setup additional callback for updating file path
	hidden_file_input.bind('change focus click', function() {
		// update the filename text
		var filename = $(this).val();
		if ( filename === '' ) {
			filename = initial_path_text;
		}
		else {
			// remove fakepath prefix
			filename = filename.split('\\').pop();
		}
		visible_filepath_text_control.val( filename );
	});
	
	// do an initial update
	hidden_file_input.change();
}
