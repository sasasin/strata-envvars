# `--serve`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（DeepSeek-V4.1 専用エンジン） |
| オプション | `--serve` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

DeepSeek-V4.1 モデル pack をロードし、標準入力からの生成要求を受け付ける常駐モードに切り替えます。`serve` は TCP/HTTP サーバーを直接開くオプションではありません。Strata の `serve/server.py` がエンジンを子プロセスとして起動し、`READY`、`GEN` / `GENI`、`T`、`DONE` などの行プロトコルで通信します。

## 使い方

```sh
strata-dsv41 --pack /models/deepseek-v4.1/maya-ds4 --serve
```

これはビルド済み `strata-dsv41` と、対応するモデル pack を使う場合の例です。ソースでは `--pack` が必須です。実際のエンジンは `STRATA_BUILD_DSV41=ON` などの条件で生成され、標準構成で必ずビルド・配布されるとは限りません。

## 値と既定値

- `--serve` は parser が `serve_mode = true` に設定するだけで、値を読みません。既定値は `false`（serve 以外の実行モード）です。
- 同じフラグを複数回指定しても同じ真偽値を設定します。値を続けて書く構文や `--serve=false` は実装されていません。
- このモードでは `--pack` が必要ですが、`--ids` などの単発実行入力は不要です。`--serve` を省略し、別の操作入力も指定しない場合は usage を表示して終了コード 2 になります。

## 実行時の動作

1. parser は `--serve` を認識すると serve mode を有効にします。オプション順は固定されず、`--pack` などと同じ parser で処理されます。
2. pack が空なら usage を標準エラーへ出して終了コード 2。pack があれば `Model::load` でモデルをロードし、失敗時は `maya-ds4: <理由>` を標準エラーに出して終了コード 1 です。
3. モデル情報を標準エラーへ出した後、`serve(...)` に入り、モデル情報行と `READY <context> stop` を標準出力へ出して flush します。その後、標準入力の行を処理します。
4. `GEN` はテキスト生成、`GENI` は画像を含む要求に使われます。応答 token は `T <id>`、要求完了は `DONE ...` の行で標準出力へ返され、要求ごとの進捗・統計は標準エラーへ出ます。`QUIT` または入力の終端で serve loop を終了します。

`--serve` と他の engine オプションを併用すると、pack のロード設定や生成モードの関連設定は serve 呼び出しへ渡されます。たとえば `--eos`、`--dspark`、`--dspark-conf` は serve 関数にも値が渡ります。`--temperature`、`--seed` 等は parser では受け付けますが、serve 呼び出しの引数には含まれず、サーバープロトコル側の要求設定と同じものではありません。

## 適用条件と副作用

- CMake の `STRATA_BUILD_DSV41` が既定では OFF で、DeepSeek-V4.1 用の `strata-dsv41` target は CUDA/HIP 等のビルド条件内で生成されます。ビルド設定によっては同 target がなく、GPU backend なしの分岐は host-side benchmark のみを生成します。
- serve mode はモデルとデバイス資源をロードして要求を処理します。標準入力・標準出力をプロトコル用に占有するため、対話端末から人が直接入力する用途ではなく、サーバー等からの子プロセス利用が想定されています。
- `STRATA_DS4_SLOT_KEEP` が非ゼロなら会話 slot の保持が有効になります（未設定時は無効）。有効時は既定で `<pack>/slots` を使い、会話状態を `.bin` と `.meta` に保存・再利用し、期限切れ・不整合ファイルや容量超過分を削除します。保持件数・保存先・期限・容量は `STRATA_DS4_SLOT_CAP`、`STRATA_DS4_SLOT_DIR`、`STRATA_DS4_SLOT_DAYS`、`STRATA_DS4_SLOT_GB` で変わります。
- serve mode の各要求後と終了時に `m.save_profile()` が呼ばれます。プロファイルの既定パスは `<pack>/expert-profile.bin` で、`--expert-profile none` なら空にできます。保存内容や失敗時の扱いの全ては、このオプション調査では追跡していません。
- `--pack-info` と同時に指定した場合は先行する pack-info 分岐で終了するため serve mode には入りません。

## 出力とエラー

- 起動時の parser エラー（未知のオプション、値が必要な別オプションの値欠落）は usage / エラーメッセージを標準エラーに出し、終了コード 2 です。
- `GEN` / `GENI` 以外の未知プロトコル行や不正な生成行には `ERR ...` を標準出力へ返し、プロセスは要求ループを継続します。画像要求で vision tower がない場合なども `ERR` とキャンセル形式の `DONE` を返します。
- モデルロード失敗は終了コード 1。正常な `QUIT` または入力終端では serve 関数は 0 を返します。
- 起動後の `READY`、生成 token、`DONE` は標準出力、説明・進捗・統計は標準エラーに分けられます。プロトコルと同じ stdout に通常ログを混ぜない構成です。

## 根拠

- `src/dsv41/ds4_main.cpp:85-94` — usage に記載された serve モードと、`--pack` を含む呼び出し形。
- `src/dsv41/ds4_main.cpp:318-325,646-659` — serve の開始出力、入力ループ、`QUIT`、プロトコルエラー処理。
- `src/dsv41/ds4_main.cpp:917-958` — `DONE` と要求統計、要求後・終了時の profile 保存、終了コード。
- `src/dsv41/ds4_main.cpp:1190-1207,1263-1273,1282-1296` — フラグ parser、必須 pack、単発入力要件の除外、model load、serve 分岐。
- `src/dsv41/ds4_main.cpp:331-353,636-644,932-957` — slot 永続化の環境変数、既定値、終了時の書き込み。
- `serve/server.py:1284-1298,2198-2205` — サーバー側の engine 起動応答と `GEN` / `GENI` 標準入力送信。
- `CMakeLists.txt:797-812,2377-2386` — `strata-dsv41` の build option と条件付き target。

調査時に既存 `strata-dsv41` バイナリの `--help` は実行していません。記述は上記 commit の parser とソースに基づき、Release 配布物の有無は確認対象外です。
