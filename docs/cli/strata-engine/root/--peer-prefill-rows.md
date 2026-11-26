# `--peer-prefill-rows`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--peer-prefill-rows` |
| 別名 | なし |
| 値 | 符号付き整数 `N`（prompt chunk 内で peer GPU に割り当てる routed rows の上限として渡す値） |

## 役割

`--peer-device` で指定した peer GPU が、prompt 処理時に担当する expert の routed rows 数を調整します。0 は peer に prompt rows を計算させず、primary GPU に残します。正数は `Prefill::set_peer` に行数上限として渡されます。省略時は `--prefill` の chunk サイズと top-k `K` から `chunk × K / 2` を計算します。ただし compact peer-prefill 経路では実装が上限を chunk 全体の `T_max × K` に置き換えるため、この値は上限として機能しません。

## 使い方

```sh
# 2 番目の GPU を peer tier にし、prompt rows の上限値を指定してエンジンを起動する
strata --pack /path/to/model.gguf --peer-device 1 --peer-prefill-rows 2048
```

peer GPU 自体を有効にする `--peer-device` がない場合、この値から peer prefill は設定されません。

## 値と既定値

- parser は `N` を `std::atoll` で `int64_t` に変換します。オプション固有の範囲検査は見つかりませんでした。値を省略すると parser が stderr に `--peer-prefill-rows needs a value` を出して終了コード 2 で終了します。
- 未指定時の内部値は `-1` です。peer が有効で値が 0 以外なら、正数はその値、0 未満は `o.prefill_chunk * K / 2` に変換されます。したがって `-1` 以外の負数も同じ既定計算になります。
- 0 は peer prefill の初期化呼び出し自体を飛ばします。正数または既定計算値は `T_max × K` 以下に制限され、少なくとも 1 行に丸められます（compact 経路では後述のとおり上限が全行数に置き換わります）。
- 同じ option を複数回指定した場合、parser は各出現で同じ値を代入するため、後の指定が残ります。

## 実行時の動作

peer が有効で値が 0 以外の場合、エンジンは prompt path の初期化時に行数を算出し `sp.set_peer(&peer, rows, err)` を呼びます。peer 側に保持された expert のうち、その prompt chunk で選択された expert の routed rows を peer に割り当て、残りを primary が処理します。行数上限に収まらない peer 保持 expert は、その chunk では上限超過として peer 対象から外されます。peer-streamed expert の rows は上限判定を通らず peer 側に加算されます。

CUDA/HIP と SYCL の実装には `STRATA_PF_PEER_COMPACT` による compact 経路があります。CUDA/HIP と SYCL のどちらも、環境変数未指定時は compact が有効で、compact 時には `cap_rows` が `T_max × K` に再設定されます。このため通常の compact 経路では `--peer-prefill-rows` の正数や既定値は上限を狭めません。CUDA/HIP ではさらに P2P がない場合 compact が強制されます。SYCL では P2P が必須です。`STRATA_PF_PEER_COMPACT=0` で compact を無効にした場合に初期化時の値が上限として残りますが、CUDA/HIP では P2P 経路も必要です。

## 適用条件と副作用

- `--peer-device` で peer GPU を有効にした場合だけ prompt peer path の設定対象になります。`--layer-split` または `--expert-cache-device1..3` と peer tier の併用は、別の起動時検査で拒否されます。
- peer prefill の初期化に失敗したとき、CUDA/HIP と SYCL の呼び出し元は stderr に失敗理由と「prompt path stays on the primary GPU」を出し、エラーをクリアして primary GPU 側で続行します。GPU メモリ不足、サポートする prompt kernel がない場合などが拒否経路です。
- CUDA/HIP は P2P がない場合、デフォルトでは mapped host memory 経由の経路を利用できます（`STRATA_PF_PEER_HOST=0` なら拒否）。SYCL は P2P がない場合に peer prefill を拒否します。
- 初期化では peer GPU 上に prompt 用 device buffer を確保します。P2P がない CUDA/HIP 経路では mapped pinned host buffers も確保し、確保できなければ primary 側へフォールバックします。

## 出力とエラー

- peer path の確保に失敗すると、CUDA/HIP または SYCL の `set_peer` がエラー理由を返し、呼び出し元が stderr に `strata serve: <理由> - the prompt path stays on the primary GPU` を出します。起動はこの失敗だけでは中断されません。
- 行数上限が適用される経路では、chunk ごとに上限を超えた expert 数が集計され、stderr の peer timing 出力に `over the cap` として表示されます。
- parser で値が欠けた場合は stderr に不足を表示し、終了コード 2 で終了します。

## 根拠

- `engine/src/program/generate.cpp:922-924` — 未指定値 `-1` と prompt rows の説明。
- `engine/src/program/generate.cpp:1432-1433`、`engine/sycl/src/program/generate.cpp:989-990` — CUDA/HIP と SYCL の help 文。
- `engine/src/program/generate.cpp:3842-3847,4205-4209`、`engine/sycl/src/program/generate.cpp:2170-2173` — parser の値取得、`atoll` 変換、引数不足時の終了。
- `engine/src/program/generate.cpp:13143-13153`、`engine/sycl/src/program/generate.cpp:7608-7613` — 0 以外の場合の値計算、peer path 設定、primary 側への fallback。
- `engine/src/program/generate.cpp:5268-5290` — 他 resource 値の検査と、peer device と layer split / remote expert cache の併用拒否。`peer_prefill_rows` 自体はこの範囲の範囲検査に含まれません。
- `engine/src/prefill/prefill.cpp:3333-3369`、`engine/sycl/src/prefill/prefill.cpp:2243-2248` — peer の有効性、CUDA/HIP の host route、kernel・pack 条件、SYCL の P2P / MMQ 条件。
- `engine/src/prefill/prefill.cpp:3373-3378,3412-3417`、`engine/sycl/src/prefill/prefill.cpp:2249-2253,2307-2313` — `cap_rows` の clamp と compact 時の全行数への置換。
- `engine/src/prefill/prefill.cpp:6059-6078`、`engine/sycl/src/prefill/prefill.cpp:4090-4108` — chunk ごとの peer expert 選択、上限判定、peer-streamed rows の扱い。
- `engine/src/prefill/prefill.cpp:7992-8005`、`engine/sycl/src/prefill/prefill.cpp:5758-5770` — stderr timing 出力と `over the cap` の表示。
- `engine/src/prefill/prefill.cpp:3501-3537,3538-3545`、`engine/sycl/src/prefill/prefill.cpp:2368-2385` — host buffer / peer buffer 確保失敗と初期化時の stderr 出力。
- `engine/src/prefill/prefill.cpp:3337-3339`、`engine/sycl/src/prefill/prefill.cpp:2246-2248` — P2P がない場合の backend 差。

調査範囲は上記の Strata ソースにある CUDA/HIP および SYCL の parser と prompt peer path です。実際の性能差、ハードウェアごとの転送性能、全 build 構成での動作は測定・実行していません。
