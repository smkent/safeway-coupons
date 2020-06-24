pipeline {
    agent any
    triggers { cron('H 11 * * *') }
    options {
        buildDiscarder(logRotator(numToKeepStr: '30', artifactNumToKeepStr: '30'))
    }
    stages {
        stage('Build') {
            steps {
                withCredentials([file(credentialsId: 'safeway-coupons-config', variable: 'SAFEWAY_COUPONS_CONFIG')]) {
                    sh '''
                    docker build --no-cache -t safeway-coupons .

                    docker run --rm -t -v "${SAFEWAY_COUPONS_CONFIG}":"/app/config.ini" safeway-coupons /app/safeway-coupons -c /app/config.ini
                    '''
                }
            }
        }
    }
}
