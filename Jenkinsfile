pipeline {
    agent any

    environment {
        DOCKER_REGISTRY = 'your.registry.com'
        APP_NAME = 'ai-ops-backend'
        IMAGE_TAG = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Python Lint & Test') {
            agent {
                docker {
                    image 'python:3.10-slim'
                }
            }
            steps {
                sh '''
                cd backend
                pip install -r requirements.txt
                pytest tests/ --junitxml=report.xml
                '''
            }
            post {
                always {
                    junit 'backend/report.xml'
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    dockerImage = docker.build("${DOCKER_REGISTRY}/${APP_NAME}:${IMAGE_TAG}", "-f backend/Dockerfile backend/")
                }
            }
        }

        stage('Push Image') {
            steps {
                script {
                    docker.withRegistry("https://${DOCKER_REGISTRY}", 'docker-credentials-id') {
                        dockerImage.push()
                        dockerImage.push('latest')
                    }
                }
            }
        }

        stage('Blue/Green Deployment') {
            steps {
                sh '''
                chmod +x scripts/blue_green_deploy.sh
                ./scripts/blue_green_deploy.sh
                '''
            }
        }

        stage('Integration Test (Newman)') {
            agent {
                docker {
                    image 'postman/newman:alpine'
                }
            }
            steps {
                sh '''
                if [ -f postman_collection.json ] && [ -f postman_environment.json ]; then
                  newman run postman_collection.json -e postman_environment.json
                else
                  echo "Skip Newman: postman_collection.json or postman_environment.json not found."
                fi
                '''
            }
        }
    }

    post {
        failure {
            echo 'Deployment failed, triggering rollback...'
            sh '''
            chmod +x scripts/rollback.sh
            ./scripts/rollback.sh
            '''
        }
        success {
            echo 'Pipeline successfully completed.'
        }
    }
}
