# `--serve`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン） |
| オプション | `--serve` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

モデルと推論用リソースを起動時に読み込み、プロセスを終了せずに複数の推論要求を順に処理するモードです。この `generate.cpp` の実装では TCP listener を開く処理は確認できず、要求は stdin から受け取り、準備完了・token・完了情報などを stdout に返す行プロトコルです（`src/program/generate.cpp:7497-7517, 11166-11170`）。

## 使い方

pack を使う通常 parser での例です。`/path/to/pack` は利用可能な Strata pack のディレクトリに置き換えます。

```sh
strata --pack /path/to/pack --serve --spec 4 --prefill 2048 --expert-cache auto
```

この起動後、クライアントは stdin に `GEN <max_new> <id,id,...>` を一行で送り、stdout の `READY`、`T <id>`、`DONE ...` などを読み取ります。終了時は `QUIT` を送ります。`STOP` は実行中要求の停止要求です（`src/program/generate.cpp:7499-7517, 10956-10965, 12020`）。

## 値と既定値

値を取らず、指定すると `Options::serve` を `true` にします。未指定時の値は `false` です（`src/program/generate.cpp:720-721, 2637`）。重複指定を拒否する処理はなく、同じ boolean 値を再設定します。値を後置すると別の引数として解釈され、未知の引数なら usage を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2416-2424, 2787-2793`）。

serve では要求ごとの prompt token を stdin から受け取るため、起動時の `--tokens` は必須ではありません。未指定なら内部で token `248045`、`max_new=1`、`stop_eos=true` を初期値として設定します（`src/program/generate.cpp:3168-3178`）。

## 実行時の動作

- 通常 parser は `--serve` を `o.serve` に設定します。起動時にモデル・重み・expert cache 等を初期化した後、`READY <context> stop` を stdout に出し、要求待ちに入ります（`src/program/generate.cpp:2637, 11166-11170`）。
- 通常の要求は `GEN <max_new> <id,id,...>`、画像要求は `GENI` 系の入力を受け付けます。prompt の進捗・再利用量を示す `RESUME` / `PP` / `REUSED`、token ごとの `T <id>`、終了時の `DONE ...`、処理できない要求の `ERR <message>` を stdout に返します。token は verify window 完了後に出力され、decode は greedy です（`src/program/generate.cpp:7499-7517, 12289`）。不正な要求形式は `ERR expected: ...` を返して次の行へ進みます（`src/program/generate.cpp:12289`）。
- stdin を専用 thread で読みます。`STOP` は停止 flag として扱われ、`QUIT` または stdin の EOF で serve loop を抜けます（`src/program/generate.cpp:10907-10965, 12020, 15685`）。
- conversation checkpoint は既定で最大 6 個を保持し、会話の prompt の一部を後続要求で再利用できます。これは `--prompt-cache` 等で変更できます（`src/program/generate.cpp:725-729, 891-895`）。モデルや cache の準備・保持と要求処理のため GPU/host RAM を使用します。
- `--batch` を併用すると複数 slot の要求を同時に扱う別経路が有効になります。`--serve` 単独では batch slot は有効になりません（`src/program/generate.cpp:658-660, 11972-12014`）。

## 適用条件と副作用

- 通常 parser の serve 経路では `--spec` が 2 以上、`--prefill` の chunk が正であることが必要です。該当しない場合は `strata serve: needs --spec T and --prefill CHUNK ...` を stderr に出し、終了コード 2 で終了します。expert cache が充填可能であることも前提で、graph-hit 経路を使う構成では `--expert-profile` による profile と fillable hit data が追加で必要です（`src/program/generate.cpp:8354-8359`）。
- `--serve` を指定すると engine が要求待ちを続け、モデルと関連 cache をプロセス内に保持します。単発 generate と異なり、要求が来るまで stdin 待ちとなります。`--serve` 自体の socket bind やファイル出力は確認できません。profile 保存などは `--expert-profile-save` 等の別オプションを指定した場合の副作用です（`src/program/generate.cpp:7497-7517, 10907-10965, 15685`）。
- `--model` または `--native` の GGUF が Qwen3.6 family (`qwen35moe`) と識別される build では、option parser より先に `src/qwen35` 実装へ委譲されます。その場合は通常 parser の上記 validation・動作記述ではなく、[Qwen3.6 用 `--serve`](../qwen36/--serve.md) の文書が該当します（`src/program/generate.cpp:2393-2407`）。

## 出力とエラー

通常 parser では起動成功時に stdout へ `READY <context> stop` を出します。要求単位の結果・失敗は stdout の `T` / `DONE` / `ERR` などで通知され、診断や起動時 warning は stderr に出ます（`src/program/generate.cpp:7499-7517, 11166-11170, 12289`）。

不足する `--spec` / `--prefill` 等は起動時に拒否され終了コード 2 です。未知の CLI 引数も stderr に `unknown argument: ...` と usage を出し終了コード 2 になります（`src/program/generate.cpp:8354-8359, 2787-2793`）。要求内容が不正な場合は `ERR` を返して loop を継続する経路が確認できます（`src/program/generate.cpp:12289`）。

## 根拠と調査範囲

- parser と既定値: `src/program/generate.cpp:720-721, 2416-2424, 2637`
- serve の自動 token 初期化と起動要件: `src/program/generate.cpp:3168-3178, 8354-8359`
- protocol、入力 thread、準備完了、終了: `src/program/generate.cpp:7497-7517, 10907-10965, 11166-11170, 12020, 15685`
- family dispatch: `src/program/generate.cpp:2393-2407`

調査は上記 commit の source checkout と `docs/cli/README.md` の索引記載に基づきます。同一 revision の既存バイナリによる `--help` は実行しておらず、build・GPU 実行・テストも行っていません。Release 配布物での挙動はこの調査では確認していません。
