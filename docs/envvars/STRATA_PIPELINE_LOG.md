# `STRATA_PIPELINE_LOG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--pipeline-windows 2` の pipelined decode 中に、window の draft chain と verifier verdict を stderr に記録する診断用フラグです。CUDA 実装では verdict と出力 token ID も出し、SYCL 実装では verdict の短い行を出します。フラグはパイプラインの計算や判定を変えず、ログ出力を有効にします。

この名前を読む Strata 本体の箇所は CUDA 側 `src/program/generate.cpp` と SYCL 側 `sycl/src/program/generate.cpp` の各 1 箇所です。ほかに SYCL verifier のコメントが名前を挙げますが、それ自体は読み取りではありません（`sycl/src/core/verify.cpp:4062`）。

## 値と判定

値の内容は parse されず、`getenv()` が null かどうかだけで判定します。ただし `pipe_dbg_env()` を通るため、実際に値が返るには `STRATA_PIPELINE_DEBUG` も有効である必要があります。

| 設定 | `STRATA_PIPELINE_LOG` の結果 |
|---|---|
| `STRATA_PIPELINE_DEBUG` が未設定、空文字、または先頭文字が `0` | `pipe_dbg_env()` は null を返すため無効。`STRATA_PIPELINE_LOG` の値は参照されない |
| `STRATA_PIPELINE_DEBUG` が空でなく、先頭文字が `0` 以外。`STRATA_PIPELINE_LOG` が未設定 | 無効 |
| 同上で `STRATA_PIPELINE_LOG` が設定済み | 有効。空文字、`0`、`false` を含む任意の値で有効 |

`STRATA_PIPELINE_DEBUG` は先頭文字だけを見ます。大文字小文字や数値としての妥当性は検査しません。例として `STRATA_PIPELINE_DEBUG=0anything` は無効、`false` や `1anything` は有効です。根拠: `src/program/generate.cpp:461-467`, `sycl/src/program/generate.cpp:298-303`。

## 有効になる条件

- 実行経路が Strata の CUDA または SYCL `strata serve` パイプライン decode であること。通常の serial decode、batch decode、単独 GPU などではこのログ箇所に到達しません。
- CUDA では `--pipeline-windows` が正で、layer split が複数 stage で成立し、stage 数が split 数と整合して `pipe` が成立すること（`src/program/generate.cpp:10000-10005`）。SYCL では `--pipeline-windows` が正で、2 stage の layer split が成立すること（`sycl/src/program/generate.cpp:7325-7329`）。
- request ごとの `pl_pw >= 2` かつ GDN snapshot が使えること（CUDA `pl_snap_ok`、SYCL `pl_snap2[0] != nullptr`）。その request が cancellation 済みでなく、生成上限にも達しておらず、serial decode にする理由がないことも必要です（CUDA `src/program/generate.cpp:16087-16103`; SYCL `sycl/src/program/generate.cpp:11037-11053`）。
- `pl_pw` は通常 `--pipeline-windows` の値ですが、debug helper 経由の `STRATA_PIPELINE_SWITCH` がファイルから `pw=` を読み、request 単位で 0–2 に上書きできます（CUDA `src/program/generate.cpp:14777-14800`; SYCL `sycl/src/program/generate.cpp:10428-10451`）。

`STRATA_PIPELINE_DEBUG` が有効でも、これらの条件を満たさず pipelined decode の本体へ入らなければ、この変数によるログは出ません。CUDA/SYCL で split 条件や snapshot 確保方法に差があります。

## 実行時の詳細

`pipe_dbg_env()` は関数内 `static const bool` として `STRATA_PIPELINE_DEBUG` の判定を初回 helper 呼び出し時に cache します。未設定、空文字、または先頭文字 `0` なら全 `STRATA_PIPELINE_*` debug/tuning 変数について null を返します。helper の判定後に環境を変えても gate は再評価されません（CUDA `src/program/generate.cpp:461-467`; SYCL `sycl/src/program/generate.cpp:298-303`）。

`STRATA_PIPELINE_LOG` 自体も、decode が pipelined loop に入った際に `static const bool pl_log` として一度だけ判定されます。helper が返すポインタが null でなければ true なので、明示的な空文字も有効です。以後プロセス内で環境を変更しても反映されません（CUDA `src/program/generate.cpp:16098-16126`; SYCL `sycl/src/program/generate.cpp:11048-11071`）。

有効時、chain を作った際に `strata pipeline: chain ...` を stderr に出し、各 verdict で `strata pipeline: verdict ...` を出します。CUDA は verdict 行に続けて確定した出力 token ID も同じ行に書きます。SYCL の verdict 行には token ID は含みません（CUDA `src/program/generate.cpp:16501-16505,16622-16628`; SYCL `sycl/src/program/generate.cpp:11509-11513,11620-11622`）。この環境変数が直接引き起こす終了・失敗経路はありません。

## 根拠

- 共通の debug gate: `src/program/generate.cpp:461-467`, `sycl/src/program/generate.cpp:298-303`。
- 値の取得と cache: `src/program/generate.cpp:16098-16126`, `sycl/src/program/generate.cpp:11048-11071`。
- CUDA/SYCL のパイプライン条件: `src/program/generate.cpp:10000-10005,10281-10317,16087-16103`; `sycl/src/program/generate.cpp:7325-7329,7580-7602,11037-11053`。
- 診断出力: `src/program/generate.cpp:16501-16505,16622-16628`; `sycl/src/program/generate.cpp:11509-11513,11620-11622`。
- debug 用 request switch による `pl_pw` 上書き: `src/program/generate.cpp:14777-14800`; `sycl/src/program/generate.cpp:10428-10451`。
