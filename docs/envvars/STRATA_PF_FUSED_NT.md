# `STRATA_PF_FUSED_NT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の Strata 作業ツリーは `main...origin/main` で、`git status --short --branch` に未コミット変更は表示されなかった。

## 役割

ネイティブ GGUF の MoE prompt fused kernel で、通常のカーネルに加えて NT = 256（256 threads）のカーネル群を設定し、利用可能ならその経路を選びます。これはネイティブ pack の fused prompt 経路の追加 opt-in です。環境変数を設定しただけでは経路は有効にならず、ネイティブ fused 経路自体が選ばれ、デバイス上で必要な全 NT = 256 カーネルの設定に成功する必要があります。

この変数は CUDA の実装で読み取られます。HIP 側には NT = 256 の設定処理がなく、`STRATA_PF_FUSED_NT` による選択は行われません。CUDA ビルドでは NT = 256 カーネルの device code が含まれます（`docs/DETAILS.md:1535-1541`）。

## 値と判定

読み取りは `std::getenv("STRATA_PF_FUSED_NT")` の後に `std::atoi` を適用し、戻り値が整数 `256` と等しいかで判定します。文字列全体や末尾は検査されず、設定値の有無だけを見る判定でもありません。

| 値 | `atoi` の判定結果 | NT = 256 の要求 |
|---|---:|---|
| 未設定 | 読み取り結果が null | しない |
| 空文字 | 0 | しない |
| `256` | 256 | する |
| `+256`、先頭空白を含む ` 256` | 256 | する |
| `256xyz`、`256.0` | 256（数値接頭部を変換） | する |
| `0256` | 256（10進変換） | する |
| `255`、`0`、`-256`、数字で始まらない文字列 | 256 以外 | しない |

コードは変換エラーや範囲外の値を個別に検出せず、`atoi(v) == 256` の結果だけを使います。無効値に対する警告やエラーはこの読み取り箇所からは出ません。

既定では要求しません。`STRATA_PF_FUSED_F16` が先頭文字 `1` で有効なら、`nt256_requested()` はその要求との OR を返すため、`STRATA_PF_FUSED_NT` が未設定または 256 以外でも NT = 256 系の設定を試みます。その場合 `setup_nt()` は F16 版の NT カーネルを設定します。したがって、通常の整数精度 NT カーネルだけをこの変数で選ぶには F16 側の指定が有効でない必要があります（`src/prefill/moe_fused_iq.cu:1714-1738`）。

## 有効になる条件

次の条件がそろった場合に、prompt のネイティブ fused 経路が NT = 256 カーネルを使えます。

- CUDA ビルドであり、NT = 256 の setup 分岐がコンパイルされている。HIP の `dev_info()` は別分岐で戻るため、この変数による NT setup を行いません（`src/prefill/moe_fused_iq.cu:1688-1739,1771-1807`）。
- `STRATA_PF_FUSED_NT` の変換結果が 256、または `STRATA_PF_FUSED_F16` が先頭文字 `1`。ただし環境値は遅延評価時に一度だけキャッシュされます（`src/prefill/moe_fused_iq.cu:1714-1738`）。
- GPU が `dev_info()` の通常のネイティブ kernel 対応条件を満たす。NT setup は `d.ok` の場合だけ試されます。通常の CUDA 経路では sm_80 以上で、Turing (sm_75) の特別経路は NT setup の前に戻ります（`src/prefill/moe_fused_iq.cu:1817-1845`）。
- GPU 上で gate/up と down の全対象フォーマットについて `setup_nt()` が成功し、各 kernel の属性取得、動的 shared memory の設定、occupancy 問い合わせが成功する。`STRATA_PF_FUSED_Q2N` で Q2_0 gate/up を追加している場合は、その NT kernel の設定成功も必要です（`src/prefill/moe_fused_iq.cu:1701-1712,1837-1845`）。
- Prompt のレイヤーが `fused_nat` 経路に入ること。実際の選択では MMQ plan 上の対象レイヤー、stream-all 経路、peer GPU 不使用、native pack、Hadamard 変換なし、`native_supported()` のフォーマット対応が必要です（`src/prefill/prefill.cpp:4192-4223`）。`native_supported()` 自体も `STRATA_PF_FUSED`、デバイス、フォーマット、既定 opt-in 条件などを確認します。従って本変数単独では native fused prompt を有効化しません（`src/prefill/moe_fused_iq.cu:1976-2015`）。

setup が失敗すると `d.occ_nt` は 0 のままで、stderr に `prefill fused experts (native): STRATA_PF_FUSED_NT=256 is not available here` と出ます。NT カーネルを使う wide batch は利用可能にならず、呼び出し側は通常サイズの batch にし、対応する通常 native kernel を使います。setup 失敗そのものではプロセス終了しません（`src/prefill/moe_fused_iq.cu:1837-1845,2141-2141`; `src/prefill/prefill.cpp:4278-4279,4307-4320`）。

## 実行時の詳細

`nt256_requested()` が最初に呼ばれたときに `STRATA_PF_FUSED_NT`（および OR 条件の `STRATA_PF_FUSED_F16`）を読み、`static const bool` に保存します。`dev_info()` もデバイスごとの `DevInfo` を `done` とともにキャッシュします。よって、これらの判定後にプロセス環境を変更しても、既に評価済みの値や設定は再評価されません（`src/prefill/moe_fused_iq.cu:1685-1686,1716-1722,1771-1777`）。

成功した NT setup は `occ_nt` に occupancy を保存します。`native_wide()` は `occ_nt > 0`（または別機能の warp-specialized kernel）を返し、prompt 側は `STRATA_PF_BATCH` が通常上限より大きい場合に限って WideBatch を選びます。通常の batch 呼び出しでも `occ_nt > 0` なら NT = 256 kernel が選ばれます。NT wide 経路では gate/up と down を NT = 256 の launch で実行し、launch error は `ck(..., "experts_native (NT = 256)")` に渡されます（`src/prefill/moe_fused_iq.cu:1926-1943,2025-2034,2141-2172`; `src/prefill/prefill.cpp:4273-4279,4307-4320`）。

この環境変数専用の「有効」ログはありません。設定不能時の stderr 警告のほか、テストプログラムはこの値を直接読み、要求された NT kernel が設定されなければ `STRATA_PF_FUSED_NT / _F16 / _WS: those kernels are not set up on this device (skipped)` と表示して skip code 77 を返します。これはテスト専用の挙動で、通常実行時のログではありません（`tests/cuda/prefill_fused_iq_test.cpp:675-685`）。CMake はこの値を `prefill_fused_iq_test_nt256` テストの環境に `256` として渡します（`CMakeLists.txt:2320-2323`）。

`docs/DETAILS.md` はこの switch を「256 threads、SM あたり 2 blocks」の CUDA prompt-expert kernel とし、著者計測値として MoE 1 layer / 3,256 tokens の 8.27 ms を記載しています。同じ表の記載によれば `STRATA_PF_FUSED_NT=256` は出力 bit を保つとされています。これは同資料が報告する CMP 170HX 上の値で、Strata 上で再測定した結果ではありません（`docs/DETAILS.md:1524-1542`）。

## 根拠

- 候補一覧: `STRATA_PF_FUSED_NT` は `docs/envvars/000_envvers.md:1213` に掲載。
- 本番コードの環境読み取り、整数変換、F16 との OR: `src/prefill/moe_fused_iq.cu:1714-1738`。
- CUDA デバイス・カーネル setup と設定不能時の警告: `src/prefill/moe_fused_iq.cu:1688-1739,1771-1845`。
- native fused 経路の条件と環境変数との関係: `src/prefill/moe_fused_iq.cu:1976-2015`; `src/prefill/prefill.cpp:4192-4223`。
- batch / kernel 選択と実行: `src/prefill/moe_fused_iq.cu:2025-2034,2141-2172`; `src/prefill/prefill.cpp:4273-4320`。
- 直接参照の全件は `rg -n --hidden --glob '!\.git/**' 'STRATA_PF_FUSED_NT'` で確認。ほかに CMake のテスト設定、CUDA テストコード、コメント、ヘッダー、`docs/DETAILS.md` に参照があります。テストの getenv はテストの skip 判定であり、本番動作の根拠には使用していません。
