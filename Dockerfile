FROM debian:7.7

MAINTAINER Rob McQueen

# Install Python
# RUN apt-get update
RUN apt-get upgrade
# RUN apt-get install  python-dev  
RUN apt-get install python-virtualenv 
  

  

# Install Ansible
RUN mkdir /opt/ansible && virtualenv /opt/ansible/venv && \
  /opt/ansible/venv/bin/pip install ansible

# ADD . /build
# COPY .ansible-test /build
# WORKDIR /build

CMD /opt/ansible/venv/bin/ansible-playbook -i inventory.yml \
    -c local -s -e testing=true -e role=$DOCKER_TEST_ROLE \
    role playbook.yml; /bin/bash