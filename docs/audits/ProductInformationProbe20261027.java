// Offline check of the real internal product DTO. Uses the compiled backend and test mocks.
// Run from repo root after the backend tests (PowerShell):
// [xml]$x=Get-Content backend/target/surefire-reports/TEST-com.aimall.backend.internal.Bm25RetrieverTest.xml
// $cp=($x.testsuite.properties.property | Where-Object name -eq 'java.class.path').value
// java -cp $cp docs/audits/ProductInformationProbe20261027.java
import com.aimall.backend.entity.Product;
import com.aimall.backend.mapper.ProductMapper;
import com.aimall.backend.internal.InternalToolController;
import com.aimall.backend.internal.Bm25Retriever;
import java.util.List;
import java.util.Map;
import static org.mockito.Mockito.*;

class ProductInformationProbe20261027 {
    public static void main(String[] args) {
        Product product = new Product();
        product.setId(1L);
        product.setName("audit product");
        product.setStatus("ON_SALE");
        product.setOrigin("France");
        product.setShipFrom("Shanghai");
        product.setMaterial("cotton");
        product.setProductionDate("2026-10-01");
        ProductMapper mapper = mock(ProductMapper.class);
        when(mapper.selectById(1L)).thenReturn(product);
        var controller = new InternalToolController(mapper, null, null, null, null);
        var request = new InternalToolController.ProductDetailBody();
        request.setProductId(1L);
        Map<String, Object> detail = controller.productDetail(request).getData();
        var missing = List.of("origin", "shipFrom", "material", "productionDate").stream()
            .filter(key -> !detail.containsKey(key)).toList();
        System.out.println("Missing factual fields in actual AI product_detail DTO: " + missing);
        var bm25 = new Bm25Retriever();
        var hits = bm25.search("退货期限", List.of(new Bm25Retriever.Document(
            1L, 1L, null, "POLICY", "退货期限是七天。", "退货政策")), 20);
        double score = hits.get(0).score();
        System.out.printf("Calibration observation only: BM25 raw=%.6f, evidence at scale=8: %.6f%n",
            score, score / (score + 8.0));
        if (!missing.isEmpty()) {
            System.out.println("FAIL: populated product facts are dropped before reaching the AI tool");
            System.exit(1);
        }
        System.out.println("PASS");
    }
}
