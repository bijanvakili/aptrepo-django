
# puppet module to deploy apt repo dependencies on Ubuntu Linux

class aptrepo::params {
  $owner = 'vagrant'
  $group = 'vagrant'
  $virtualenv_dir = '/opt/aptrepo_pyenv'
  $requirements_path = '/vagrant/tools/share/python/requirements.txt'
  $install_build_dependencies = false
}

class aptrepo (
  $owner = $aptrepo::params::owner,
  $virtualenv_dir = $aptrepo::params::virtualenv_dir,
  $requirements_path = $aptrepo::params::requirements_path,
  $install_build_dependencies = $aptrepo::params::install_build_dependencies  
) inherits aptrepo::params 
{
  package {
    [ 'python-apt', 'python-debian', 'python-pyme' ]:
    ensure => installed,
  }
  
  # build dependencies
  if $install_build_dependencies {
    package {
      [ 'make', 'gettext', 'librsvg2-bin', 'rhino', 'pylint', 'sqlite3'] :
      ensure => installed,
    }
  }

	class { 'python' :
	  version    => 'system',
	  pip        => true,
	  virtualenv => true,
	}
	
	python::virtualenv { $virtualenv_dir :
    venv_dir     => $virtualenv_dir,
    owner        => $owner,
    group        => $group,
	  ensure       => present,
	  systempkgs   => true,
	  version      => 'system',
	  requirements => $requirements_path,
	}
}

node /^vagrant.*/ {
  class { 'aptrepo':
    install_build_dependencies => true
  }
}
