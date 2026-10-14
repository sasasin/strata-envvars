# `STRATA_NO_NVFP4_512`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

CPU native-expert 経路で NVFP4 の gate/up 行と down 行を計算するとき、AVX-512 実装を選ばないための開発・診断用スイッチです。GPU 側の NVFP4 カーネルやモデル形式の選択は変更しません。AVX-512 を止めた場合も、条件を満たせば AVX2 実装へ進みます。

## 値と判定

両方の読み取り箇所は `std::getenv("STRATA_NO_NVFP4_512") == nullptr` を判定し、値を数値や文字列として parse しません。

| 状態 | AVX-512 NVFP4 経路 |
|---|---|
| 未設定 | CPU が AVX-512 対応なら候補になる |
| 任意の値を設定 | 無効。`1`、`0`、`false`、空文字のどれでも同じ |

gate/up 用と down 用で別々の関数内 `static const bool` に保存されます。各経路で初回に評価された後は、そのプロセス内で環境変数を変更しても再評価されません。

## 有効になる条件

環境変数が未設定でも、AVX-512 経路には次の条件があります。

- `STRATA_NATIVE_EXPERTS` を有効にしてビルドした CPU native-expert 実装が使われている。
- 対象の projection が NVFP4 である。
- `cpu_avx512_ok()` が true を返す。これは CPU の AVX-512 F/BW/VL/DQ/VNNI/VBMI 機能と OS の AVX-512 状態保存を確認し、`STRATA_FORCE_AVX2=1` や `STRATA_FORCE_ISA` の上限も反映する。
- 行の要素数 `n` が NVFP4 のブロックサイズ（64）の倍数で、ブロック数が実装上限以内（`nvfp4_512_fits(n)`）。

この条件を満たさない場合、変数の未設定・設定にかかわらず AVX-512 NVFP4 関数は呼ばれません。環境変数で AVX-512 を止めた場合、次に AVX2 対応 CPU かつ行サイズが `nvfp4_256_fits(n)` を満たせば AVX2 NVFP4 経路が使われます。さらにそれも使えない場合は ggml-cpu の `vec_dot` 経路へ進みます。AVX2 経路は別変数 `STRATA_NO_NVFP4_256` でも止められます。

## 実行時の詳細

CPU pool は native expert の gate/up 処理から `native_gu_rows()`、down 処理から `native_down_rows()` を呼びます。両関数は AVX-512 対応とこの変数の未設定を確認した後、NVFP4 の projection と行サイズが適合すれば、それぞれ `nvfp4_512_gu_rows()` / `nvfp4_512_rows()` に処理を渡します。設定済みの場合はこの分岐を飛ばし、続く AVX2 判定または ggml-cpu の行 dot 処理を行います。

この判定自体によるログ出力はありません。NVFP4 設計資料には `STRATA_NO_NVFP4_512=1` で ggml-cpu に fallback するとありますが、現行コードでは AVX2 が利用可能で寸法条件を満たすと AVX2 実装へ fallback します。資料の「ggml-cpu」は AVX2 fallback を記載していない点に注意が必要です。資料の速度表は、CPU の 1 expert の gate+up、1280 rows × 2560、cache-resident の測定であり、この環境変数を使ったエンジン全体の性能を示すものではありません。

## 根拠

- 環境変数の判定と gate/up の AVX-512 → AVX2 → ggml-cpu の順序: `src/kernels/cpu/native_expert.cpp:195-229`。
- down の同じ順序: `src/kernels/cpu/native_expert.cpp:258-278`。
- CPU pool からの gate/up・down 呼び出し: `src/kernels/cpu/pool.cpp:705-719`。
- AVX-512 CPU/OS 機能チェックと ISA 上限: `src/kernels/cpu/expert_layout.cpp:25-74`。
- native experts のビルド条件と AVX-512 / AVX2 ソースの ISA 指定: `CMakeLists.txt:1258-1272,1317-1342`。
- 64 要素単位と最大ブロック数の寸法判定: `src/kernels/cpu/nvfp4_avx512.cpp:152`、AVX2 版は `src/kernels/cpu/nvfp4_avx2.cpp:161`。
- NVFP4 資料の記述と測定条件: `docs/NVFP4.md:166-180`。
