# `STRATA_PF_FUSED_F16`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の native fused prompt-expert kernel で、256-thread kernel の整数 int8 積を F16 行列積に切り替える opt-in です。F16 積は FP32 accumulator に加算されます。実装資料は出力が丸めレベルで変化すると説明しています。値を有効にすると `STRATA_PF_FUSED_NT=256` を別途指定しなくても 256-thread 経路が要求されます（`src/prefill/moe_fused_iq.cu:1714-1722`）。

この変数だけでは fused prompt-expert 経路そのものは有効になりません。通常の fused 経路の選択条件、native pack の形式、対象デバイスが先に適合する必要があります。

## 値と判定

| 環境値 | 判定 | 結果 |
|---|---|---|
| 未設定 | 無効 | F16 版を要求しない |
| 空文字 | 無効 | `getenv` は非 null だが先頭文字が `'1'` ではない |
| 先頭文字が `1` | 有効 | `1`, `10`, `1anything` など。文字列全体の parse はしない |
| その他 | 無効 | `0`, `true`, ` 1` など |

比較は大文字小文字を区別する先頭 1 文字との比較です。数値変換、範囲検査、無効値の警告や fallback はありません。判定は `f16c_requested()` の function-local `static const bool` に保存されます。また 256-thread 有効性とデバイス情報も cache されるため、最初の判定後にプロセス環境を変えても再評価されません。CLI 引数や設定ファイルによる上書きはこの読み取り箇所にはありません（`src/prefill/moe_fused_iq.cu:1716-1722,1771-1777`）。

## 有効になる条件

- CUDA build であること。HIP の `dev_info()` は HIP 用 device 情報を設定した後に return し、CUDA 専用の `nt256_requested()` / `setup_nt()` に進みません。F16 launch も `#if !defined(__HIPCC__)` の中です（`src/prefill/moe_fused_iq.cu:1782-1807,1837-1845,1933-1942`）。
- CUDA compute capability 8.0 以上であること。7.5 以下は 256-thread setup 判定より前に return し、コメント上も F16 経路は sm_80+ のみです（`src/prefill/moe_fused_iq.cu:1817-1830,228-231`）。
- その GPU 上で必要な F16 版 native kernel 群の attribute 設定と occupancy 判定がすべて成功すること。失敗時は `occ_nt` が 0 のままとなり、stderr に `prefill fused experts (native): STRATA_PF_FUSED_NT=256 is not available here` を出します。この文言は `_F16` が要求された場合にも同じです。WS kernel も使えない場合、基礎の native fused kernel が利用可能なら通常の int8 native kernel に進みます（`src/prefill/moe_fused_iq.cu:1701-1711,1837-1845,2113-2138`）。
- native fused prompt-expert がその層で選ばれること。呼び出し元は `stream_all`、peer device 不使用、native layout、Hadamard folded gate/up・down なし、MMQ plan 対象か fused-only 対象、対応形式などを確認します。層やチャンクがこの経路を取らなければ本変数の F16 kernel は使われません（`src/prefill/prefill.cpp:4192-4205,4217-4223`）。
- `STRATA_PF_FUSED_WS=1` による warp-specialized kernel が setup 済みの場合はそちらを先に launch します。WS が選ばれない wide 経路では、`STRATA_PF_FUSED_F16` が有効なら F16 版を起動し、無効なら 256-thread int8 版を起動します（`src/prefill/moe_fused_iq.cu:1926-1942,2154-2172`）。

## 実行時の詳細

`dev_info()` は device ごとの `DevInfo` を初回に初期化し、`done` を立てた後はその情報を再利用します。CUDA sm_80+ では `nt256_requested()` が `_F16` の値を含めて 256-thread 経路を要求し、`setup_nt()` は F16 値が有効なら各 native kernel type の F16 template を attribute / shared-memory / occupancy 検査します。どれか一つでも失敗すれば `occ_nt` を無効にします。その場合も WS が利用可能なら WS を使い、WS も無効なら後続の native fused 呼び出しは通常の int8 kernel に進みます（`src/prefill/moe_fused_iq.cu:1771-1777,1837-1851,1701-1711,1736-1738,2113-2138`）。

実行時は prompt layer の native fused path が expert kernels を呼び、F16 が有効で WS が選ばれていなければ F16 template を起動します。F16 kernel はデコードした重みと activation を F16 にし、16 要素単位の F16 products を FP32 accumulators に積算します（`src/prefill/moe_fused_iq.cu:557-561,1933-1942,2143-2172`）。fused prompt path が実際に選ばれた場合、呼び出し元は一度だけ stderr に `strata: prompt experts on the fused int8 kernels (STRATA_PF_FUSED=1, #136)` と出します。これは F16 選択を個別に示すログではありません（`src/prefill/prefill.cpp:4252-4257`）。

既定の unset 状態は F16 無効です。無効値を理由とした警告はありません。kernel setup 失敗時は前記 stderr ログが出て、`occ_nt` が無効になります。実装資料は F16 経路で出力が丸めレベルで変化すると記載し、著者測定として CMP 170HX の MoE 1 layer / 3,256 tokens で 7.90 ms を挙げています。この値は Strata 内の今回の調査で測定したものではありません（`docs/DETAILS.md:1535-1544`）。

## 根拠

- 唯一の本番環境読み取りと cache、256-thread 要求への連動: `src/prefill/moe_fused_iq.cu:1714-1722`。
- CUDA/HIP・GPU世代ごとの初期化と kernel setup、失敗ログ: `src/prefill/moe_fused_iq.cu:1771-1845`。
- F16 template の内容と launch 分岐: `src/prefill/moe_fused_iq.cu:557-561,1926-1942,2143-2172`。
- 呼び出し元の native fused 経路と観測ログ: `src/prefill/prefill.cpp:4192-4205,4217-4223,4252-4257`。
- 測定条件を含む既存資料: `docs/DETAILS.md:1535-1544`。
