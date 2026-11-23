# `strata-inkling --native`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（CUDA/HIP root） |
| オプション | `--native` |
| 別名 | `--model` |
| 値 | モデルファイルまたはモデルディレクトリのパスを1つ取る。`.strata`、HF safetensors、GGUF を扱う loader へ渡される。 |

## 役割

モデルの場所を指定し、通常の生成・serve・bench・selfcheck・参照 logits 評価などのモデルを使う実行経路に渡します。`--native` 自体は形式や内容を検証せず、`InkModelFile::open` がパスの性質に応じた loader を選びます。`--info` と `--export-tokenizer` はモデルパスを使わない別モードです（`engine/src/inkling2/ink_main.cpp:388-405,544-558`）。

## 使い方

```sh
# モデルを指定して通常の生成を実行
strata-inkling --native ./model.strata

# モデルを指定して line protocol の serve モードを起動
strata-inkling --serve --native ./model.strata

# モデルを指定して benchmark モードを実行
strata-inkling --bench --native ./model.strata

# モデルを指定して selfcheck を実行
strata-inkling --selfcheck --native ./model.strata
```

## 値と既定値

値を1つ必須とします。値が続かない場合は `missing value after --native` を stderr に出し、終了コード 2 で終了します。値の内容に対する parser 段階の検証、既定パス、空文字の拒否はありません。複数回指定すると `cfg.model_path` が都度代入されるため、後の指定値が残ります（`engine/src/inkling2/ink_main.cpp:379-383,404-405`）。

モデルを必要とする通常生成・serve の経路で値が空なら `error: --native <model.strata|hf_dir|model.gguf> is required` を stderr に出して終了コード 2 になります。bench / KLD 評価 / dump-ref はこの共通の空値検査より先に分岐し、空パスで loader を呼ぶため、同じ必須エラーにはなりません。selfcheck はモデルパスなしでも backend の selfcheck を実行できます（`engine/src/inkling2/ink_main.cpp:544-561`; `cmd_selfcheck` は `:101-127`、bench は `:130-145`、KLD 評価は `:254-280`、dump-ref は `:323-332`）。

## 実行時の動作

parser は値を `ServeConfig::model_path` に保存します（`engine/src/inkling2/ink_main.cpp:404-405`; フィールド定義 `engine/src/inkling2/ink_serve.h:431-438`）。その後、実行モードの優先順で selfcheck、KLD 評価、dump-ref、bench を選び、それらに該当しなければ通常のモデルロードへ進みます。複数モードのフラグを同時に指定した場合も、この分岐順で最初に成立する経路が選ばれます（`engine/src/inkling2/ink_main.cpp:544-558`）。

通常生成と serve は `InkModelFile::open` に値を渡します。パスが safetensors と判定されると safetensors adapter、GGUF magic が検出されると GGUF adapter、それ以外は Strata reader に渡されます。HF safetensors は単一ファイルまたは、対応する index / safetensors ファイルを含むディレクトリを検出する実装です（`engine/src/inkling2/ink_manifest.h:454-477`; 判定 `engine/src/inkling2/ink_safetensors_loader.h:117-135`, `engine/src/inkling2/ink_gguf_loader.h:285-287`）。ロード後は backend 初期化に同じモデルを使い、通常生成では slot を確保して入力 token の処理と生成を行い、serve では serve loop に渡します（`engine/src/inkling2/ink_main.cpp:556-578,580-613`; serve のモデル名表示と起動処理 `engine/src/inkling2/ink_serve.h:441-485`）。

## 適用条件と副作用

モデルロードを行うモードでのみ使用されます。`--info` または `--export-tokenizer` が同時に指定されると、先にそれらのモードへ分岐するため `--native` の値は使われません（`engine/src/inkling2/ink_main.cpp:544-549`）。selfcheck では省略可能です。モデル形式の判定はファイル名だけでなく safetensors のパス判定および GGUF magic によって行われ、該当しないパスは Strata reader に渡ります（`engine/src/inkling2/ink_manifest.h:462-477`）。

このオプションが指定するパスからモデルデータを読み込み、backend 初期化に使います。サーバーモードではロードされたモデルの basename を `INFO` protocol 出力に含めます（`engine/src/inkling2/ink_serve.h:467-485`）。パスがネットワーク上のものか、特定の OS / backend で許されるかは、この parser 定義だけでは判定できません。

## 出力とエラー

通常ロードでモデルを開けない場合は `open: <理由>` を stderr に出し、終了コード 1 で終了します。serve モードでは同じ失敗理由を protocol の `ERR open: ...` として出力します。backend 初期化失敗は通常モードで `init: <理由>`、serve では `ERR init: <理由>` となり、いずれも終了コード 1 です（`engine/src/inkling2/ink_main.cpp:556-569`）。selfcheck はロード失敗時に `[selfcheck] FAIL open: ...`、bench / KLD 評価 / dump-ref は `open: ...` を stderr に出します（`engine/src/inkling2/ink_main.cpp:101-109,130-145,254-280,323-332`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:379-405` — parser の値取得、`--native` と `--model` の同一フィールドへの代入、値欠落時の終了。
- `engine/src/inkling2/ink_main.cpp:544-569` — モード分岐、空パスの共通エラー、loader 呼び出しと open / init 失敗出力。
- `engine/src/inkling2/ink_main.cpp:101-127,130-145,254-280,323-332,575-613` — selfcheck、bench、評価系、通常生成での値の使用。
- `engine/src/inkling2/ink_manifest.h:440-477` — モデルハンドルの対応形式と loader の振り分け。
- `engine/src/inkling2/ink_safetensors_loader.h:117-135`、`engine/src/inkling2/ink_gguf_loader.h:285-287` — safetensors / GGUF のパス判定。
- `engine/src/inkling2/ink_serve.h:431-438,441-485` — serve 設定のモデルパス、モデル basename を含む INFO と serve 初期化。
