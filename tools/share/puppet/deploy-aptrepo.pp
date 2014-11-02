
# puppet module to deploy apt repo dependencies on Ubuntu Linux

class aptrepo::params {
  $owner = 'vagrant'
  $virtualenv_dir = '/vagrant/pyenv'
  $requirements_path = '/vagrant/aptrepo/requirements.txt'
}

class aptrepo (
  $owner = $aptrepo::params::owner,
  $virtualenv_dir = $aptrepo::params::virtualenv_dir,
  $requirements_path = $aptrepo::params::requirements_path  
) inherits aptrepo::params 
{
  package {
    [ 'python-apt', 'python-debian', 'python-pyme', 'sqlite3' ]:
    ensure => installed,
  }

	class { 'python' :
	  version    => 'system',
	  pip        => true,
	  virtualenv => true,
	}
	
	python::virtualenv { $virtualenv_dir :
    venv_dir     => $virtualenv_dir,
    owner        => $owner,
	  ensure       => present,
	  version      => 'system',
	}
	
	python::requirements { $requirements_path : 
	  virtualenv => $virtualenv_dir,
	  owner => $owner
	}
}

node /^vagrant.*/ {
  class { 'aptrepo':
    requirements_path => '/vagrant/aptrepo/tools/share/puppet/requirements.txt'
  }
}
