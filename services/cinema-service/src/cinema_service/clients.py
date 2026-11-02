import httpx
from .contracts import SalesSnapshot


class RemoteFailure(Exception):
    def __init__(self, status, message="Dịch vụ phụ thuộc chưa sẵn sàng"):
        self.status = status
        super().__init__(message)


class Clients:
    def __init__(self, settings, http): self.settings, self.http = settings, http

    def call(self, origin, method, path, **kwargs):
        if len(self.settings.service_key) < 32: raise RemoteFailure(503)
        try:
            response = self.http.request(method, origin+path, headers={"X-Service-Key": self.settings.service_key},
                timeout=5, follow_redirects=False, **kwargs)
            if response.status_code != 200:
                message = response.json().get("detail", "Dịch vụ phụ thuộc từ chối thao tác")
                raise RemoteFailure(response.status_code, message if isinstance(message,str) else "Dữ liệu không hợp lệ")
            return response.json()
        except (httpx.RequestError, ValueError) as exc:
            raise RemoteFailure(503) from exc

    def booking(self, method, path, **kwargs):
        return self.call(self.settings.booking_origin, method, "/internal/v1/sales"+path, **kwargs)

    def catalog(self, method, path, **kwargs):
        return self.call(self.settings.catalog_origin, method, "/internal/v1"+path, **kwargs)

    def close(self, show_id, epoch):
        data = self.booking("POST", f"/{show_id}/close", json={"epoch":epoch})
        if data.get("epoch") != epoch or data.get("is_open") is not False: raise RemoteFailure(503,"Chưa xác nhận đóng bán")
        return data

    def state(self, show_id, seat_id=None):
        params = {"seat_id":seat_id} if seat_id is not None else {}
        data = self.booking("GET", f"/{show_id}/state", params=params)
        if not {"epoch","is_open","sales_version","live_holds","pending_bookings","bookings","seat_references"} <= data.keys():
            raise RemoteFailure(503,"Thiếu trạng thái xử lý hold/đơn")
        return data

    def install(self, snapshot, epoch):
        snapshot = SalesSnapshot.model_validate(snapshot)
        digest = snapshot.digest()
        data = self.booking("POST", f"/{snapshot.showtime_id}/import", json={"epoch":epoch,"snapshot":snapshot.model_dump(mode="json"),"digest":digest})
        if data.get("showtime_id") != snapshot.showtime_id or data.get("acknowledged") is not True or data.get("digest") != digest or data.get("sales_version") != snapshot.sales_version or data.get("epoch") != epoch:
            raise RemoteFailure(503,"Chưa nhận đủ ACK cấu hình bán vé")
        return data

    def open(self, snapshot, epoch):
        snapshot = SalesSnapshot.model_validate(snapshot)
        data = self.booking("POST", f"/{snapshot.showtime_id}/open", json={"epoch":epoch,"sales_version":snapshot.sales_version,"digest":snapshot.digest()})
        if data.get("sales_version") != snapshot.sales_version or data.get("is_open") is not True or data.get("digest") != snapshot.digest() or data.get("epoch") != epoch:
            raise RemoteFailure(503,"Chưa xác nhận mở bán")
        return data


    def reference(self,binding_id,action,reference):
        data=self.catalog("POST",f"/schedule-bindings/{binding_id}/{action}",json={"reference":reference})
        if data.get("id")!=binding_id or data.get("reference")!=reference or data.get("state")!=("CONFIRMED" if action=="confirm" else "RELEASED"):
            raise RemoteFailure(503,"Chưa xác nhận vòng đời tham chiếu Catalog")
        return data
