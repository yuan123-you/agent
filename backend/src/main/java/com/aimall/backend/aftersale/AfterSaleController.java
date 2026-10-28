package com.aimall.backend.aftersale;

import com.aimall.backend.common.*;
import com.aimall.backend.entity.AfterSale;
import lombok.RequiredArgsConstructor;
import org.springframework.http.*;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import java.util.*;

@RestController
@RequestMapping("/api/v1/after-sales")
@RequiredArgsConstructor
public class AfterSaleController {
    private final AfterSaleService service;
    private final AfterSaleEvidenceStorage storage;
    private String role(Authentication auth) {return auth.getAuthorities().stream().map(a->a.getAuthority().replaceFirst("^ROLE_", "")).filter(r->Set.of("ADMIN","MERCHANT","CUSTOMER").contains(r)).findFirst().orElse("NONE");}
    @GetMapping("/my") public ApiResponse<?> my(@AuthenticationPrincipal Long user,Authentication auth,@RequestParam(required=false) String status,@RequestParam(required=false) Long orderId,@RequestParam(defaultValue="1") long page,@RequestParam(defaultValue="20") long size){return ApiResponse.ok(service.list(user,role(auth),false,status,orderId,page,size));}
    @GetMapping("/manage") public ApiResponse<?> manage(@AuthenticationPrincipal Long user,Authentication auth,@RequestParam(required=false) String status,@RequestParam(required=false) Long orderId,@RequestParam(defaultValue="1") long page,@RequestParam(defaultValue="20") long size){return ApiResponse.ok(service.list(user,role(auth),true,status,orderId,page,size));}
    @GetMapping("/eligibility") public ApiResponse<?> eligibility(@AuthenticationPrincipal Long user,@RequestParam Long orderId){return ApiResponse.ok(service.eligibility(user,orderId));}
    @GetMapping("/quote") public ApiResponse<?> quote(@AuthenticationPrincipal Long user,@RequestParam Long orderId,@RequestParam Long orderItemId,@RequestParam String serviceType,@RequestParam int quantity){return ApiResponse.ok(Map.of("maxRefundAmount",service.quote(user,orderId,orderItemId,serviceType,quantity)));}
    @PostMapping public ApiResponse<?> apply(@AuthenticationPrincipal Long user,@RequestBody AfterSaleService.Apply request){AfterSale c=service.apply(user,request,null,null);return ApiResponse.ok(service.view(user,"CUSTOMER",c));}
    @GetMapping("/{id}") public ApiResponse<?> detail(@AuthenticationPrincipal Long user,Authentication auth,@PathVariable Long id){String role=role(auth);return ApiResponse.ok(service.view(user,role,service.authorized(user,role,id)));}
    @PostMapping("/{id}/actions") public ApiResponse<?> act(@AuthenticationPrincipal Long user,Authentication auth,@PathVariable Long id,@RequestBody AfterSaleService.Command command){String role=role(auth);return ApiResponse.ok(service.view(user,role,service.act(user,role,id,command)));}
    @PostMapping(value="/evidence",consumes=MediaType.MULTIPART_FORM_DATA_VALUE) public ApiResponse<?> upload(@AuthenticationPrincipal Long user,@RequestParam("file") MultipartFile file){return ApiResponse.ok(Map.of("token",storage.save(user,file)));}
    @GetMapping("/{id}/evidence/{token}") public ResponseEntity<byte[]> evidence(@AuthenticationPrincipal Long user,Authentication auth,@PathVariable Long id,@PathVariable String token){
        String role=role(auth);AfterSale c=service.authorized(user,role,id);var data=service.view(user,role,c);
        if(!((List<?>)data.get("evidence")).contains(token))throw new BizException(2003,"凭证不属于该售后单");
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).header("X-Content-Type-Options","nosniff").contentType(token.endsWith(".png")?MediaType.IMAGE_PNG:MediaType.IMAGE_JPEG).body(storage.read(c.getUserId(),token));
    }
}
