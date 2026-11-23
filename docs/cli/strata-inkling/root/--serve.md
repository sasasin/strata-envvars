# `--serve`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling` |
| オプション | `--serve` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

モデルと backend を初期化した後、標準入力から要求を受け取り標準出力へ応答する常駐エンジンモードを選びます。Strata の server 側プロセスなどが行単位プロトコルでエンジンを制御する用途です。このフラグ自身が HTTP サーバーやネットワーク待受を開始するわけではありません。

## 使い方

```sh
# モデルを読み込み、行プロトコルの入力を待つ
strata-inkling --serve --native /models/example.strata

# 並列要求用の slot 数などを指定して起動する例
strata-inkling --serve --native /models/example.strata --parallel 4 --max-context 8192
```

起動すると `INFO` と `READY` を標準出力へ出し、標準入力のプロトコルコマンドを処理します。対話プロンプトを表示する通常の生成モードとは異なります。

## 値と既定値

`--serve` は値を取らず、指定されるたび `mode_serve` を `true` にします。重複指定しても同じフラグ状態です。単独の値範囲や `--serve` 専用の validation はありません。`--native <model.strata|hf_dir|model.gguf>` は別の必須引数で、モデルを指定しない場合はエラーになります。

## 実行時の動作

引数解析後、`--info`、`--export-tokenizer`、`--selfcheck`、`--kld-eval`、`--dump-ref`、`--bench` の分岐が `--serve` の実行分岐より先に評価されます。そのため、これらのモード指定も同時に与えると、記載順にかかわらず先に該当した処理が選ばれ、serve loop には入りません。これらの組み合わせを拒否する相互排他 validation はありません。`--version` と `--help` は引数解析中に即時終了します。

serve mode ではモデルを開き backend を初期化し、`--parallel` 等から決まる slot 数分の slot を確保してから `INFO` と `READY` を出力します。その後 stdin の行を処理し、要求に対する token や完了情報を stdout に行単位で返します。要求の同時処理数は `--parallel`（範囲外は 1..64 に補正）で決まり、`--max-context`、backend 選択、画像用 `--vision`、draft 関連設定なども同じ `ServeConfig` / backend 設定を通じて serve loop に渡されます。

## 適用条件と副作用

このモードはモデルファイルを開き、CUDA/HIP 等のビルド済み backend を初期化して GPU/CPU リソースを使用します。設定された並列 slot を確保できない場合は起動に失敗します。`--vision` が指定される場合、Vision shard は serve loop 内で probe され、失敗時は stderr に無効化理由を出します。

`--serve` 自体によるファイル書き込みや socket/listener の生成は確認できません。実装は stdin reader と stdout protocol writer を使用します。ネットワーク API を提供する場合は、それを起動する上位 server プロセスが担当します。

## 出力とエラー

通常起動時の `INFO` / `READY` およびプロトコル応答は stdout に出力され、各行は flush されます。モデルパスが未指定なら stderr に `error: --native ... is required` を出して終了コード 2、モデルを開けない・backend 初期化に失敗する場合はプロトコル行 `ERR open: ...` / `ERR init: ...` を stdout に出して終了コード 1 です。slot 確保失敗も `ERR alloc_slot ...` を出して終了コード 1 です。未知のオプションは stderr に `unknown option` を出して終了コード 2、値を要する他オプションの値が欠けている場合も終了コード 2 です。

## 根拠

- `engine/src/inkling2/ink_main.cpp:371-404` — serve 状態の初期値、引数走査、`--serve` の値なし parser 登録。
- `engine/src/inkling2/ink_main.cpp:488-502` — help usage と未知オプション時の終了経路。
- `engine/src/inkling2/ink_main.cpp:540-573` — serve error 設定、他モードとの分岐順、モデル open/backend init/serve loop の呼び出し。
- `engine/src/inkling2/ink_main.cpp:551-568` — モデル必須条件と open/init 失敗時の出力・終了コード。
- `engine/src/inkling2/ink_serve.h:41-50` — stdout へのプロトコル出力と行ごとの flush。
- `engine/src/inkling2/ink_serve.h:441-485` — 並列 slot 数、Vision probe、slot 確保、`INFO` / `READY` 出力。
- `engine/src/inkling2/ink_serve.h:628-719` — stdin から受ける行プロトコルコマンドの処理と不正・未知コマンド応答。
- `engine/src/inkling2/ink_serve.h:341-395` — stdin を行単位で読む入力 reader。
