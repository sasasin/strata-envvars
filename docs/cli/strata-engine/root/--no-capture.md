# `--no-capture`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main` で、調査開始時の作業ツリーに未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--no-capture` |
| 別名 | なし |
| 値 | 値なしのフラグ |

## 役割

層の実行に CUDA graph の capture/replay を使わず、各層を通常の呼び出しで直接実行します。主に通常のグラフ経路と比較する診断・測定用です。ソースでは初期値が `false` で、指定時に `true` になります（`src/program/generate.cpp:507,2504`）。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --no-capture --no-pool
```

`--no-capture` 自体は値を取りません。`--no-pool` も付ける必要があります。`strata generate` の usage は `--pack` と `--tokens` を示し、`--no-capture` を「層を直接実行する」フラグとして列挙しています（`src/program/generate.cpp:806-811,887`）。

## 値と既定値

- 値は不要です。`--no-capture` を指定するだけで有効になります（`src/program/generate.cpp:2504`）。
- 省略時は `false` で、通常の capture/replay 経路を使います（`src/program/generate.cpp:507,6952-6962,7471-7478`）。
- 重複指定を拒否する処理はなく、繰り返しても同じ真偽値を設定します（`src/program/generate.cpp:2416-2422,2504`）。
- 値を取る parser 分岐ではありません。別の未知引数は `unknown argument` を stderr に出し、usage を表示して終了コード `2` になります（`src/program/generate.cpp:2787-2792`）。

## 実行時の動作

指定時は `session_capture` を呼ばず、token graph の `session_capture_token` も呼ばない条件になります（`src/program/generate.cpp:6952-6962,7471-7478`）。各 token の層処理では `session_token(...)` を選び、層を順に `block_layer(...)` へ渡します。指定しない場合は、作成済み token graph があれば `session_run_token`、なければ `session_loop` を選びます（`src/program/generate.cpp:15932-15950`、`src/core/session.cpp:805-832`）。

この直接実行経路には CPU expert pool の hook がありません。そのまま `--no-capture` だけを指定すると routed experts が計算されないため、engine は `--no-pool` も要求し、満たさない場合は理由を stderr に出して終了コード `2` で拒否します。したがって併用時の意図は CPU pool を使わない GPU-only の実行です（`src/program/generate.cpp:6965-6979`）。

## 適用条件と副作用

- `--stage-timing` は capture 内で CUDA event を記録できないことを理由に、`--no-capture` なしでは終了コード `2` で拒否されます。併用時は stage timing を有効化し、初期化失敗なら stderr に `stage_timing_enable failed` を出して終了コード `1` です（`src/program/generate.cpp:6881-6894`）。
- `--dump-layers` はこの経路では staging buffer が埋まらないため、`--dump-halves` は graph に capture されるデータであるため、それぞれ併用すると stderr に理由を出して終了コード `2` で拒否されます（`src/program/generate.cpp:6981-6994`）。
- `--sync-every-layer` は `session_token` に渡され、指定すると各層後に stream を同期します。非同期 GPU error を層単位で検出する診断動作です（`src/program/generate.cpp:2506,15932-15936`、`src/core/session.cpp:834-843`）。
- 有効な生成経路では model の層を GPU 上で実行し、通常の token 生成・出力処理を続けます。層の失敗は `session_token` のエラーを stderr に出し、終了コード `1` になります（`src/program/generate.cpp:15932-15937`）。
- Qwen3.5 MoE の GGUF は `src/qwen35` の別 parser へ引き渡されます（`src/program/generate.cpp:2393-2407`）。その parser に `--no-capture` はなく、通常の generate mode では未知引数として usage を表示し終了コード `2` になります。serve mode でも `--serve` より前に現れた場合は未知引数です。`--serve` の後に現れる場合は、このエンジンにない `--...` 引数を無視する処理により効果なく無視されます（`src/qwen35/q36_engine.cu:3742-3743,3782-3795`）。

## 出力とエラー

`--no-capture` 単独の成功時に専用メッセージやファイル出力を追加する処理は確認できません。通常の生成出力に加え、上記の組み合わせ違反・層実行エラーは stderr に出力されます。組み合わせ違反は終了コード `2`、層実行失敗は `1` です（`src/program/generate.cpp:6974-6994,15932-15937`）。

## 根拠と調査範囲

- parser の既定値・受理分岐・help: `src/program/generate.cpp:507,806-808,887,2416-2422,2504`。
- graph 経路の抑止と診断 option の validation: `src/program/generate.cpp:6881-6894,6952-6994,7471-7478`。
- 直接実行と失敗経路: `src/program/generate.cpp:15932-15950`、`src/core/session.cpp:805-846`。
- Qwen3.5 MoE の別 parser: `src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3742-3795`。

この文書は checkout 内のソース調査に基づきます。同一 revision のビルド済み CLI help は実行しておらず、ビルド別・GPU 別の実行結果や性能差は確認していません。
