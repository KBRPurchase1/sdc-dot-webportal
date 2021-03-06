import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders, HttpErrorResponse } from '@angular/common/http';
import { Observable } from 'rxjs';
import 'rxjs/add/operator/map';
import { environment } from '../../../../environments/environment';
import { CognitoService } from '../../../../services/cognito.service';

@Injectable()
export class LoginSyncService {
  httpOptions = {};
  baseUrl = `${window.location.origin}/${environment.ACCOUNT_LINK_URL}`
  linkAccountUrl = `${this.baseUrl}/${environment.LINK_ACCOUNT_PATH}`;
  accountLinkedUrl = `${this.baseUrl}/${environment.ACCOUNT_LINKED_PATH}`;
  resetTemporaryPasswordUrl = `${this.baseUrl}/${environment.RESET_TEMPORARY_PASSWORD_PATH}`;

  constructor(private http: HttpClient, private cognitoService: CognitoService) {
    this.httpOptions = {
      headers: new HttpHeaders({
        'Content-Type': 'application/json',
        'Authorization': ' ' + this.cognitoService.getIdToken(),
        'Access-Control-Allow-Origin': '*'
      })
    };
  }

  userAccountsLinked(): Observable<any> {
    return this.http.get(this.accountLinkedUrl, this.httpOptions)
      .map((response) => {
        return response;
      }).catch(this.handleError);
  }

  linkAccounts(username: string, password: string): Observable<any> {
    const payload = {
      'username': username,
      'password': password
    };

    return this.http.post(this.linkAccountUrl, payload, this.httpOptions)
      .map((response) => {
        return response;
      }).catch(this.handleError);
  }

  resetTemporaryPassword(username: string, currentPassword: string, newPassword: string, newPasswordConfirmation: string): Observable<any> {
    const payload = {
      'username': username,
      'currentPassword': currentPassword,
      'newPassword': newPassword,
      'newPasswordConfirmation': newPasswordConfirmation
    };

    return this.http.post(this.resetTemporaryPasswordUrl, payload, this.httpOptions)
      .map((response) => {
        return response;
      }).catch(this.handleError);
  }

  private handleError(error: HttpErrorResponse) {
    const devErrorMsg = (error.message) ? error.message :
      error.status ? `${error.status} - ${error.statusText}` : 'Server error';
    const userErrorMessage = (error.error) ? error.error['userErrorMessage'] : 'Sorry, something went wrong. Please try again later';

    console.log(devErrorMsg);
    return Observable.throw({ userErrorMessage: userErrorMessage, body: error.error});
  }
}
