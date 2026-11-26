# `--dump-layers`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジンの root 引数。通常の生成経路） |
| オプション | `--dump-layers` |
| 別名 | なし |
| 値 | 出力ファイルパス（`PATH`） |

## 役割

各処理位置について、入力残差と各層の後の残差 `R` を float32 のバイナリファイルへ順に書きます。層間のどこで参照結果と差が生じるかを調べるためのダンプです。`strata-engine` の root option であり、Qwen3.6 専用 parser の option ではありません（索引の scope は [`docs/cli/README.md`](../../README.md) の `strata-engine` 節、`000_cli_tools.md` は `engine/src/program/generate.cpp` と `qwen36/` を別 scope としています）。

## 使い方

```sh
# モデルとトークン列を指定して通常の生成経路を実行し、位置ごとの層残差を保存する
strata --native model.gguf --tokens 1,2,3 --max-new 1 --dump-layers /tmp/layers.f32
```

`--native` と `--tokens` は例示用の入力です。実際のトークン列は対象モデルに合うものを指定してください。

## 値と既定値

- `PATH` は `--dump-layers` の直後の argv 要素をそのままファイル名として受け取ります。数値形式、拡張子、空白を含むパスの追加検証はありません。引数を省略すると `--dump-layers needs a value` を stderr に出し、終了コード 2 です（`engine/src/program/generate.cpp:3842-3846,3896`）。
- 既定値は空文字列で、未指定ならダンプを作りません。明示的に空文字列を渡した場合も、後段の `empty()` 判定により有効化されません（`engine/src/program/generate.cpp:835,10683-10687`）。
- 同じ option を複数回指定した場合は `Options::dump_layers` に順次代入されるため、最後の値だけが使用されます。重複指定のエラーやパス検証はありません（`engine/src/program/generate.cpp:3896`）。

## 実行時の動作

- 指定パスを `fopen(..., "wb")` で開きます。既存ファイルは切り詰められます。開けない場合は `strata generate: cannot write <PATH>` を stderr に出し、終了コード 1 です。続けて `(n_layers + 1) * hc * n_embd` 個の float 用の pinned host staging buffer を確保し、確保失敗時はエラーを出して終了コード 1 です（`engine/src/program/generate.cpp:10683-10695`）。
- 各 `session_loop` 呼び出しで、最初のスロットに層0への入力残差 `s.R` をコピーし、次のスロットから各層 `l` の処理後の残差をコピーします。1位置あたり `(n_layers + 1) * hc * n_embd` 個の float です。デバイスから staging buffer へのコピーは CUDA stream に非同期で積まれ、session loop 後に位置単位でファイルへ書かれます（`engine/src/core/session.cpp:659-668,754-765`; `engine/src/program/generate.cpp:24310-24312,24334-24335`）。
- ファイルにヘッダーや位置番号を付ける処理はなく、`fwrite` で float 配列をそのまま追記します。従ってサイズは出力された位置数 × `(n_layers + 1) * hc * n_embd * sizeof(float)` bytes です（`engine/src/program/generate.cpp:10685,24334-24335`）。位置ごとの書き込みは通常の生成 loop で `session_loop` を通った位置が対象です。
- ダンプ中は `--no-capture` を指定できません。併用すると `session_loop` ではなく staging buffer を埋めない `session_token` が使われるため、エラーメッセージを stderr に出して終了コード 2 で拒否されます（`engine/src/program/generate.cpp:10573-10580`）。
- `--dump-layers` を指定すると、通常は条件が合えば使う fused GR カーネルを無効化します（`engine/src/program/generate.cpp:6112-6113`）。また、per-layer host work が必要なため、条件付き token graph の作成対象から外れます（`engine/src/program/generate.cpp:10977-10979,11069-11076`）。
- `--serve` は別の server 処理経路です。ダンプファイルの open は serve 分岐より前にありますが、その後の `dump_layers` の参照・`session_loop` への引き渡し・位置ごとの書き込みは通常生成経路に限られます。したがって server request のダンプ用途には使えず、指定するとパスを開いて既存ファイルを切り詰める副作用だけが発生し得ます（`engine/src/program/generate.cpp:10683-10695,11884-11905,24310-24335`）。

## 適用条件と副作用

- `session_loop` を使う captured path が対象です。`--no-capture` とは併用できません。ダンプ中のファイル出力と GPU→host copy により、通常の生成処理へ追加の I/O と転送が入ります（`engine/src/core/session.cpp:662-668,758-765`; `engine/src/program/generate.cpp:10573-10580,24334-24335`）。
- 出力は既存ファイルを上書きします。パスの親ディレクトリは作成されません（`fopen` のみ、`engine/src/program/generate.cpp:10686-10690`）。
- 通常完了時はファイルを閉じ、staging buffer を解放し、stdout に `layers dumped` と出力形状を表示します（`engine/src/program/generate.cpp:25383-25388`）。

## 出力とエラー

- ファイルを開けない場合、pinned staging buffer を確保できない場合は前述のエラーで終了します（`engine/src/program/generate.cpp:10686-10695`）。
- 各層の device-to-host copy が enqueue に失敗した場合、`session_loop` は `dump the input residual` または `dump layer <n>` を含むエラーを返し、呼び出し側は `session_loop: <error>` を stderr に出して終了コード 1 とします（`engine/src/core/session.cpp:662-668,758-765`; `engine/src/program/generate.cpp:24310-24313`）。
- `fwrite` の戻り値と layer dump の `fclose` の戻り値は検査されていません。そのため、書き込み途中や close 時の OS エラーを CLI が検出する経路は確認できません（`engine/src/program/generate.cpp:24334-24335,25383-25388`）。

## 根拠

- `engine/src/program/generate.cpp:835` — option の保存先（空文字列が既定値）。
- `engine/src/program/generate.cpp:1285-1289,3894-3898` — help の説明と parser 登録。
- `engine/src/program/generate.cpp:6112-6113,10573-10580,10683-10695,10977-10979,11069-11076` — カーネル選択、`--no-capture` 拒否、ファイル・staging buffer の準備、token graph との相互作用。
- `engine/src/core/session.cpp:659-668,754-765` — 入力残差および各層後残差の非同期コピー。
- `engine/src/program/generate.cpp:24310-24313,24334-24335,25383-25388` — 通常生成 loop での session 呼び出し、位置単位の raw 出力、正常終了時の close と表示。
- `engine/src/program/generate.cpp:11884-11905` — serve 分岐の位置。索引 `docs/cli/README.md:1036-1081,1240-1243` と `docs/cli/000_cli_tools.md:10` — tool ID と root / Qwen3.6 parser scope。

調査時に Strata checkout は `## main...origin/main` と表示され、作業ツリーの変更はありませんでした。CLI は実行せず、挙動は同一 revision のソースで確認しました。
