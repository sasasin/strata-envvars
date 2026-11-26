# `--prompt-cache-tail`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--prompt-cache-tail` |
| 別名 | なし |
| 値 | 取らないフラグ。既定値は無効 |

## 役割

`--serve` のプロンプト読み込み中、通常の turn 境界・周期 checkpoint に加えて、プロンプト終端近くの既存 chunk 境界に checkpoint を 1 つ作り、会話キャッシュへ保持します。後続リクエストが最後の保存位置より手前までの共有履歴から分岐した場合、終端まで全て読み直さずに済む位置を増やすための機能です。新しい chunk 境界や読み込み処理は作りません。

## 使い方

```sh
# 単一 GPU で server を起動し、周期 checkpoint と tail checkpoint を有効にする
strata --serve --prompt-cache 6 --prompt-cache-every 16384 --prompt-cache-tail
```

この引数は `--serve` のリクエスト prompt 読み込み経路向けです。通常の単発生成では tail checkpoint 処理に到達しません。

## 値と既定値

- 値を取らず、指定すると `prompt_cache_tail` を `true` にします。初期値は `false` です。parser は重複指定を拒否せず、同じ真偽値を再設定します（`engine/src/program/generate.cpp:1126`, `engine/src/program/generate.cpp:4111`）。
- `--prompt-cache-tail=true` のような値付き表記はこの parser のフラグ表記ではありません。未認識引数は `unknown argument` として stderr に出し、終了コード 2 で終了します（`engine/src/program/generate.cpp:4268-4273`）。
- 有効になるには `--prompt-cache` が正（既定値 6）で、`--prompt-cache-every` も正（既定値 16384）である必要があります。`--prompt-cache 0` は checkpoint を無効にし、`--prompt-cache-every 0` は周期・tail checkpoint を無効にします（`engine/src/program/generate.cpp:1086-1090`, `engine/src/program/generate.cpp:1124-1126`, `engine/src/program/generate.cpp:1329-1331`, `engine/src/program/generate.cpp:14820-14826`）。

## 実行時の動作

prompt の batched prefill が chunk を読み終えるたびに、残り token 数が現在の chunk の実サイズ `T` 以下かつ `max(1, --short-read)` より大きい場合を tail 候補とします。さらに、その prompt ですでに tail checkpoint を保存していないこと、layer-major prefill の中間位置でないこと、単一 GPU であることを確認します。周期 checkpoint と同じ位置なら通常 checkpoint として保存し、周期位置でない候補だけを tail checkpoint として印付けします（`engine/src/program/generate.cpp:14820-14826`, `engine/src/program/generate.cpp:14827-14853`）。

保存される状態は `done` token までの prefix と、その位置までの画像情報、推論状態です。キャッシュ上限を超えた場合は `--prompt-cache-spread` の有無に応じた eviction 選択へ tail の印を渡します。新しい tail checkpoint を保存すると前の tail checkpoint は削除され、tail は常に最大 1 個です。後の周期 checkpoint がその位置を引き継ぐ場合は tail の印が解除されます（`engine/src/program/generate.cpp:14595-14607`, `engine/src/program/generate.cpp:14710-14723`, `engine/src/program/generate.cpp:14725-14753`）。

## 適用条件と副作用

- `--serve` で prompt cache と周期 checkpoint が有効なときだけ候補判定が成立します。help も単一 GPU 用と説明しています（`engine/src/program/generate.cpp:1330-1331`, `engine/src/program/generate.cpp:14823-14826`）。
- multi-GPU layer split では tail 候補になりません。layer-major prefill の中間 chunk も対象外です。prefill auto chunking を含め、境界判定には要求値ではなく実際の chunk サイズ `T` が使われます（`engine/src/program/generate.cpp:14823-14826`）。
- 条件を満たさず候補が立たない場合、このフラグ専用の拒否や警告はなく、追加 checkpoint は保存されません。
- tail checkpoint は既存の会話 checkpoint 用 GPU 状態をホスト側へコピーして保持するため、追加の checkpoint 保存・保持コストが発生します。容量上限を超えた場合には既存 checkpoint の eviction が発生し得ます（`engine/src/program/generate.cpp:14604-14607`, `engine/src/program/generate.cpp:14725-14753`）。
- 同一位置の checkpoint がすでにあれば新規コピーせず、その checkpoint の利用時刻を更新します（`engine/src/program/generate.cpp:14598-14603`）。

## 出力とエラー

checkpoint のコピーがメモリ不足など回復可能な理由で失敗した場合、その checkpoint を stderr に「skipped」と記録してリクエストを続行します。GPU 同期失敗など回復不能な場合は prompt 読み込みを失敗させ、`ERR saving a conversation checkpoint failed` を出力します（`engine/src/program/generate.cpp:14843-14850`, `engine/src/program/generate.cpp:21610-21617`）。通常の tail checkpoint 保存成功を知らせる専用ログは確認できません。

## 根拠

- `engine/src/program/generate.cpp:1124-1127`, `engine/src/program/generate.cpp:1329-1332`: 既定値と help 上の適用範囲。
- `engine/src/program/generate.cpp:4111`: parser。引数なしで真偽値を有効化。
- `engine/src/program/generate.cpp:14595-14723`: checkpoint 生成、同一位置の再利用、tail 置換。
- `engine/src/program/generate.cpp:14725-14753`: 上限超過時の eviction 選択。
- `engine/src/program/generate.cpp:14820-14853`: chunk 境界での周期・tail 判定、保存失敗時の回復動作。
- `engine/src/program/generate.cpp:21610-21617`: turn/root/message/pin checkpoint の失敗表示。

調査対象 checkout の `git status --short --branch` は `## main...origin/main` で、未コミット変更はありません。調査は上記ソースに限定し、実行バイナリの help は実行していません。
