# `--tail-role-token`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ `strata` 推論エンジン（トップレベル） |
| オプション | `--tail-role-token ID` |
| 別名 | なし |
| 値 | role を表す token ID。整数として `int64_t` に変換 |

## 役割

`--serve` の会話 prompt cache で、最後の assistant turn の直前に指定 role の turn がある場合、その短い turn を会話 checkpoint に含めず、checkpoint の境界をその turn の開始位置まで戻します。Strata Terminal CLI のサーバー実装では、末尾に置く reasoning-effort turn の role (`system`) を指定し、effort の変更時にも会話部分の checkpoint を再利用できるようにする用途があります。

## 使い方

```sh
strata --pack MODEL.pack --serve --prompt-cache 4 --tail-role-token 42
```

`42` は例示値です。実際にはモデルの tokenizer で対象 role に対応する token ID を指定します。標準の `<|im_start|>` の ID は既定で `248045` ですが、役割 token ID はモデルに依存します。

## 値と既定値

- 未指定時は `-1`。値が負ならこの機能は無効です。
- parser は `std::atoll` で読み取ります。数値形式や範囲を個別に検証せず、変換結果をそのまま設定します。そのため非数値文字列や空文字列は通常 `0` となり、数字の後ろに余分な文字がある場合も厳密な形式エラーにはなりません。`0` は有効な token ID として扱われます。
- 同じ引数を複数回指定すると、引数処理ループで後に読まれた値が残ります。
- 値を省略すると `needs a value` を stderr に出して終了コード `2` で終了します。

## 実行時の動作

エンジンは `--prompt-cache` が正の値で、`--turn-token` が非負のとき、prompt 中で `--turn-token`（既定 `<|im_start|>`）に一致する最後の token を探します。そこが見つかり、`--tail-role-token` も非負なら、その直前にある turn boundary を探します。直前の boundary の次の token が指定 role ID と一致すると、最後の turn boundary を直前側へ移し、会話 checkpoint を role turn の前に置きます。一致しない場合は通常の最後の turn boundary が使われます。

したがって、値を指定しただけでは prompt cache が無効な場合や、turn boundary が見つからない場合に効果はありません。リクエスト側で `ckpt=0` が指定された場合も checkpoint 自体を作らないため、この境界移動は checkpoint には反映されません。サーバー起動引数としては `--serve` 用と help に記載されています。

`strata-terminal` は設定 `effort_position: "end"` の場合に tokenizer で `system` を encode し、その ID をこのエンジン引数として付加します。実行ファイルにオプション文字列が見つからない場合、または `system` が単一 token でない場合は引数を付加せず、reasoning effort は prompt の先頭に置かれると通知します。

## 適用条件と副作用

- 役割 token は prompt の token ID と完全一致した場合だけ境界判定に使われます。テキスト文字列を受け取る parser ではなく、モデル/tokenizer と一致する ID が必要です。
- prompt cache の checkpoint 境界と再利用可能な会話部分に影響します。生成 token、sampling 設定、モデル重みを変更するオプションではありません。
- このオプション単独によるファイル・ネットワーク・子プロセスの副作用は確認できません。会話 cache 自体の保存・再利用動作は他の `--serve` / cache 設定に従います。
- `src/program/generate.cpp` と SYCL 実装の `sycl/src/program/generate.cpp` の双方に同じ既定値・parser・境界判定があります。その他の backend や配布済み Release バイナリでの挙動は、この調査では実行確認していません。

## 出力とエラー

有効範囲外の role ID や token が prompt に存在しない場合も、専用のエラーや警告はなく、条件不一致として通常の最後の turn boundary が使われます。非数値入力も parser 独自の validation error にはならず、`atoll` の変換結果が使われます。引数自体が未知のものなら `unknown argument: ...` と usage を stderr に出し、終了コード `2` で終了します。

## 根拠

- `src/program/generate.cpp:761` — `tail_role_token` の既定値 `-1` と意図のコメント。
- `src/program/generate.cpp:928-930` — help 上の `--serve` 適用範囲と説明。
- `src/program/generate.cpp:2416-2421` — 引数値取得。値欠落時は stderr に通知して終了コード `2`。
- `src/program/generate.cpp:2667-2669` — `--turn-token` と `--tail-role-token` を `std::atoll` で設定。
- `src/program/generate.cpp:13980-13999` — prompt cache が最後の boundary を見つけ、指定 role の直前へ境界を移す条件。`ckpt=0` の扱い。
- `src/program/generate.cpp:14037` — `turn_at` を含む位置を prompt read/checkpoint の切れ目として扱う。
- `src/program/generate.cpp:2787-2792` — 未知引数のエラー出力と終了コード `2`。
- `sycl/src/program/generate.cpp:697-701,1955-1957,10595-10607` — SYCL 版の既定値、parser、境界判定。
- `serve/server.py:2974-2996,8406-8418` — `effort_position: "end"` から `system` token ID を得て engine 起動引数へ渡す処理と fallback。
