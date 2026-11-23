# `--bench`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（トップレベル） |
| オプション | `--bench` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

読み込んだ Inkling-2-Mini モデルに対して合成 prompt の prefill と greedy decode を実行し、prefill の処理速度と decode の token 速度・所要時間を表示します。実際の文章を入力して生成するモードではありません。モデル読み込みと backend 初期化の後、指定または既定の slot 数分の KV slot を確保して計測します（`engine/src/inkling2/ink_main.cpp:130-168,171-185,225-249`）。

## 使い方

```sh
# モデルで既定長（prompt 64、decode 32）のベンチマークを実行
strata-inkling --bench --native /path/to/model.strata

# 合成 prompt と decode の長さを指定
strata-inkling --bench --native /path/to/model.strata --prompt-len 128 --gen 64

# 4 slot で並列ベンチマークを実行
strata-inkling --bench --native /path/to/model.strata --parallel 4

# ビルド済み CPU backend を使う
strata-inkling --bench --native /path/to/model.strata --cpu
```

## 値と既定値

`--bench` 自体は値を取りません。ベンチの prompt 長と decode 長はそれぞれ `--prompt-len` と `--gen` で指定し、既定値は 64 と 32 です。どちらも `std::atoi` で整数化され、parser では正数チェックを行いません。同じ引数を複数回指定した場合は後の値が残ります（`engine/src/inkling2/ink_main.cpp:376,478-481`）。

`--native PATH`（alias `--model PATH`）でモデルを渡します。省略時も `--bench` 経路はモデルパスの事前チェックを通らずモデルを開こうとし、open に失敗すると `open: ...` を stderr に出して終了コード 1 になります（`engine/src/inkling2/ink_main.cpp:130-136,404-405,549-553`）。

## 実行時の動作

モデルを開き、設定された backend を初期化します。prompt 長と decode 長の合計が設定上の `max_ctx` を超える場合は、ベンチ経路で `max_ctx` を合計 + 16 に引き上げます。その後 backend の実効 context 長を得て、prompt が収まらなければ `max(1, eff_ctx - 1)` へ、decode が残り context を超えれば残り step 数へ切り詰め、stderr に通知します。各 slot に KV 領域を割り当てた後、slot ごとに値域 100〜1099 の合成 token からなる prompt を chunk 単位で処理します。最後の prefill logits から最大値の token を選び、greedy decode を実行します（`engine/src/inkling2/ink_main.cpp:137-168,171-192,194-241`）。

成功すると stdout に backend 名、モデル形式、parallel 数、GPU 数、KV 型、実際に使った prompt / gen 長、prefill throughput、decode throughput と計測秒数を出します。生成文や token 列、ベンチ結果ファイルは出力しません（`engine/src/inkling2/ink_main.cpp:243-249`）。

## 適用条件と副作用

- backend はビルド時に有効なものから選ばれ、`--cpu` を付けると CPU backend を選びます。CUDA、HIP 等のどれが使えるかは実行ファイルのビルド条件に依存します（`engine/src/inkling2/ink_backend.h:131-168`）。
- slot 数は `--parallel`（alias `--batch` / `--slots`）で設定され、1〜64 の範囲へ parser が clamp します。KV の自動選択は既定で有効で、parallel が 16 以上なら明示的に KV 型を指定していない場合 FP8_E4M3 へ切り替わります（`engine/src/inkling2/ink_main.cpp:411-412,535-538`）。
- `--draft` / `--dspark` が有効な場合、single-slot decode では条件を満たす範囲で speculative step を試し、実装が未対応または step を返さない場合は通常の forward decode に戻ります。複数 slot の場合はこの single-slot 専用経路を使わず、通常の batched decode になります（`engine/src/inkling2/ink_main.cpp:428-432,196-241`）。
- GPU 関連設定は `--bench` にも backend options として渡されます。`IK2_EP_SPLIT` は有効な `(0, 1)` の値なら設定を上書きし、`IK2_GPUS` は CLI 側で GPU 数または GPU ID 指定がないときに参照されます（`engine/src/inkling2/ink_main.cpp:505-533`）。
- モデル/backend のロードと初期化、KV 領域の確保、実際の推論計算を行うため、対象デバイスのメモリと計算資源を消費します。ソース上、このベンチ経路が出力ファイルを書き込む処理は確認できません。

## 出力とエラー

モデル open、backend init、slot 確保、prefill、decode、speculative step の各失敗は、それぞれ `open: ...`、`init: ...`、`alloc_slot N: ...`、`bench prefill err: ...`、`bench decode err: ...`、`bench spec err: ...` を stderr に出して終了コード 1 になります。context の切り詰めはエラーではなく `[bench] clamping ...` の stderr 通知です（`engine/src/inkling2/ink_main.cpp:133-145,148-163,181-183,203-218,230-232`）。

parser は値引数の欠落を `missing value after ...` として stderr に出し、終了コード 2 で終了します。未知の option も `unknown option: ...` と終了コード 2 です（`engine/src/inkling2/ink_main.cpp:379-383,499-501`）。`std::atoi` は数値形式や正数範囲をこの parser で検証しないため、負数・非数値文字列などを指定した場合の有用な測定値は保証されません。安全な利用では正の整数を指定してください（`engine/src/inkling2/ink_main.cpp:478-481`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:130-168` — モデル open、backend 初期化、context 調整、slot と計測バッファの準備。
- `engine/src/inkling2/ink_main.cpp:171-249` — 合成 prompt、prefill / greedy decode / speculative decode、計測値の出力。
- `engine/src/inkling2/ink_main.cpp:373-424,474-501,535-553` — parser、bench 関連値の既定と変換、GPU 環境変数適用、モードのディスパッチ。
- `engine/src/inkling2/ink_backend.h:17-38,131-168` — backend options の既定値とビルド条件に応じた backend 選択。

調査は上記 checkout のソースに限定しました。既存バイナリの `--help` は実行していません。性能値、backend ごとの実機挙動、ビルド生成物ごとの利用可能機能は実行環境を確認していないため記載していません。
