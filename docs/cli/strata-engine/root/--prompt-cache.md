# `--prompt-cache`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン） |
| オプション | `--prompt-cache N` |
| 別名 | なし |
| 値 | 整数。負数は0に補正される |

## 役割

`--serve` がリクエスト間に保持する会話チェックポイント数を設定します。同じ会話の次のリクエストや、同じ先頭部分を持つプロンプトで以前の状態を再利用し、プロンプトを先頭から再計算する量を減らします。既定値6、0は無効です。これはプロンプト中のチェックポイント数であり、複数会話のスナップショットをホストRAMに退避する `--conversation-cache-mib` の容量指定とは別です。`src/program/generate.cpp:725-730` `src/program/generate.cpp:891-893`

## 使い方

```sh
strata --serve --prompt-cache 6 --pack MODEL-PACK
```

エンジンの通常のモデル指定などと併用します。`--prompt-cache` 自体は `--serve` を有効にしません。

## 値と既定値

- 省略時は6。
- parser は `atoi` で整数変換し、`max(0, 値)` を設定します。負数は0になります。数値として読めない値は `atoi` の結果が0になり、整数全体を厳密に検証する分岐はありません。複数回指定した場合は引数を左から処理し、最後の値が残ります。`src/program/generate.cpp:728` `src/program/generate.cpp:2416-2421` `src/program/generate.cpp:2640`
- 値が欠けていると `<option> needs a value` を標準エラーに出して終了コード2で終了します。`src/program/generate.cpp:2418-2420`

## 実行時の動作

`--serve` 中、プロンプトの読み込みで新しいチェックポイントを作る処理は、設定値が1以上であることを確認します。キャッシュ内のチェックポイントが上限を超えると、既定では利用時刻に基づく eviction を行い、`--prompt-cache-spread` が指定されている場合はプロンプト内の位置を分散させる方式に切り替えます。`src/program/generate.cpp:9701-9711` `src/program/generate.cpp:9826-9856`

この値と関係する設定:

- `--prompt-cache-every N` は新規に読んだプロンプトの定期チェックポイント間隔（既定16384、0で無効）です。これを0にすると定期チェックポイントは作られません。`src/program/generate.cpp:747-753` `src/program/generate.cpp:9907-9931`
- `--prompt-cache-root N`（既定2048）は、先頭から読んだプロンプトに十分長い system prompt がある場合、その最初の turn 境界にも root チェックポイントを置くしきい値です。`--prompt-cache` が正で `--turn-token` が有効であることが条件です。`src/program/generate.cpp:751-756` `src/program/generate.cpp:13993-14005`
- `--prompt-cache-tail` は、`--prompt-cache` と正の `--prompt-cache-every` が有効な単一GPU serve で、既存の prefill chunk 境界に末尾近くの追加チェックポイントを最大1つ置きます。`src/program/generate.cpp:922-925` `src/program/generate.cpp:9910-9931`
- `--conversation-cache-mib` は別会話のスナップショットを退避するRAM予算です。予算が正でも `--prompt-cache 0` なら退避は無効で、その組み合わせは serve 起動時に警告されます。`src/program/generate.cpp:2956-2958` `src/program/generate.cpp:9391-9393`

## 適用条件と副作用

主なチェックポイント動作は `--serve` のリクエスト処理にあります。0以下ではチェックポイント作成を行わず、会話の継続状態を再利用・退避できません。また、`--serve` の session file の SAVE/RESTORE は `--prompt-cache > 0` を要求し、0以下の場合はその要求を拒否します。`src/program/generate.cpp:9701-9704` `src/program/generate.cpp:12094-12100`

チェックポイントは会話状態のスナップショットを保持し、個数に応じて上限管理と eviction が発生します。ヘルプは1件あたり約118 MBのRAMと説明しています。値を大きくすると保持数の上限が増えますが、実際に作られる数や実メモリ量は会話・状態に依存します。`src/program/generate.cpp:891-893`

## 出力とエラー

- `--conversation-cache-mib` が正のまま `--prompt-cache 0` とした `--serve` では、conversation caching が無効になる旨を標準エラーへ警告します。`src/program/generate.cpp:2956-2958`
- チェックポイントの保存に失敗すると、プロンプト読み込み経路は `saving a conversation checkpoint failed` と原因を含むエラーを設定し、その処理を失敗させます。`src/program/generate.cpp:9923-9929`
- 未知の引数は `unknown argument` と usage を標準エラーに出し、終了コード2です。`src/program/generate.cpp:2787-2792`

## 根拠

- parser の既定値・help 表示・値変換: `src/program/generate.cpp:725-728`、`src/program/generate.cpp:891-893`、`src/program/generate.cpp:2640`
- checkpoint 作成・保持上限・方式選択: `src/program/generate.cpp:9701-9711`、`src/program/generate.cpp:9826-9856`
- serve での相互作用と条件: `src/program/generate.cpp:2956-2958`、`src/program/generate.cpp:9907-9931`、`src/program/generate.cpp:13993-14005`
- 文書配置と scope: `docs/cli/README.md:1128-1145`（`strata-engine` のルート引数 parser と対象リンク）、`docs/cli/001_investigation.md:71-114`（オプション文書の構成と根拠規約）。

調査は指定 commit のソースと索引に限定しました。同一 revision の実行バイナリの `--help` は実行していません。Release 配布物での確認も行っていません。
