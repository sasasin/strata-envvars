# `--conversation-cache-mib`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--conversation-cache-mib` |
| 別名 | なし |
| 値 | 非負の10進整数 MiB。最大 `8796093022207` |

## 役割

`--serve` で複数クライアントの会話を交互に処理するとき、現在アクティブでない会話の状態をホスト RAM に保持する上限を MiB で指定します。会話が再び選ばれた際に保存済みの prompt/KV 状態を再利用し、prompt を先頭から読み直す量を減らします。この RAM キャッシュは `--prompt-cache` が保持する会話内チェックポイントとは別の層です。

## 使い方

```sh
# モデルをロードして serve モードで起動し、会話キャッシュの上限を 4096 MiB にする
strata --pack ./model.gguf --serve --conversation-cache-mib 4096
```

## 値と既定値

- 値は符号なしの10進整数として解析され、範囲は `0` から `INT64_MAX / (1024 * 1024)` です。MiB から byte への変換が `int64_t` を超えない上限です。
- `0` は会話の退避キャッシュを無効にします。正の値は上限であり、その量を起動時に一括確保する指定ではありません。
- 省略時の内部値は `-1` です。`--serve` で `--prompt-cache` と `--conversation-cache-slots` が有効なら、モデルのロード後に空き RAM を測って自動算出します。それ以外では `0` になります。
- 自動算出は、空き RAM から `--conversation-cache-min-free-mib` の下限を引いた値の40%、最大8192 MiB、256 MiB単位に切り下げます。算出値が1024 MiB未満、または RAM 情報を取得できない場合は `0` です。
- 同じオプションを複数回指定したときは、parser が同じフィールドへ順に代入するため最後の値が使われます。

## 実行時の動作

parser は `std::from_chars` で文字列全体を整数として読み、負数、範囲外、空値や整数でない値を拒否します。省略値 `-1` のまま `--serve` に入ると、モデルロード後の利用可能 RAM と `--conversation-cache-min-free-mib` から容量を決めます。明示値（`0` を含む）は自動調整されません。自動値のために RAM が足りない場合、stderr にキャッシュを無効にした旨を出します。

実際のキャッシュが有効になるには、容量が正で、`--conversation-cache-slots` が正で、`--prompt-cache` も正である必要があります。`--prompt-cache` の既定値は6、slots の既定値は4です。いずれかが0なら会話キャッシュは無効になり、容量を正数で指定していた場合は stderr に無効化の警告が出ます。`--prompt-cache 0` は会話キャッシュの有無にかかわらず prompt を各要求で先頭から読みます。

キャッシュは保存された会話イメージ、保持 K/V、プールの未使用領域を合わせて指定 budget 内に収めます。budget または slot 数に収まらないときは古い退避会話を追い出し、後でその会話が必要になれば prompt を再読します。実行中の RAM 下限を守れない場合も保存を拒否またはスキップし、RAM 情報が不明なら保存・復元の安全ゲートは通りません。`--memory-limit-mib`（未指定時は `STRATA_MEMORY_LIMIT_MIB`）と `--conversation-cache-min-free-mib` はこの RAM 判定に関わります。

## 適用条件と副作用

- この値の目的は `--serve` の会話退避です。通常の単発生成では会話キャッシュは作られません。
- `--layer-split` が実質1枚の GPU（`--split-device 0`）を指定し、容量・slots・prompt cache がすべて有効な場合は非対応です。stderr に理由を出し、終了コード2で起動を拒否します。複数段の layer split はこの条件の拒否対象ではありません。
- 保存状態はホスト RAM を使用します。RAM 下限を保つため、退避会話の eviction、プール領域の返却、または個別会話の保存スキップが発生することがあります。会話スナップショットのメモリ割り当てに失敗した場合、stderr に記録してその会話の退避を飛ばし、serve 処理を続けます。
- `--conversation-spill-mib` など SSD tier が有効な構成では、RAM tier から追い出された会話を SSD tier に渡す経路があります。SSD tier の動作と保存先はそれぞれのオプションで決まり、このオプション自体はファイルを書きません。

## 出力とエラー

- 値を省略すると `--conversation-cache-mib needs a value` を stderr に出し、終了コード2で終了します。
- 非負整数でない値または上限外の値では `--conversation-cache-mib needs a nonnegative integer within range` を stderr に出し、終了コード2で終了します。
- 自動容量の決定、容量不足による無効化、prompt cache / slots による無効化、実際の park / skip の状況は stderr に出力されます。park の割り当て失敗はサーバー全体の終了ではなく、その会話の保存をスキップします。

## 根拠

- `engine/src/program/generate.cpp:1086-1093` — `--serve`、`--prompt-cache`、容量 `-1`、slots 4、RAM 下限の既定値。
- `engine/src/program/generate.cpp:1293-1300` — help に記載された cache の用途と関連引数。
- `engine/src/program/generate.cpp:3842-3847,4084-4107` — 引数取得、整数全体の解析、非負・上限 validation、フィールドへの代入。
- `engine/src/program/generate.cpp:4761-4763` — prompt cache または slots が0のときの無効化警告。
- `engine/src/program/generate.cpp:4809-4813` — 1 GPU layer split と有効な会話 cache の組み合わせを拒否する経路。
- `engine/src/program/generate.cpp:13849-13883` — 自動容量の適用条件、明示値を保持する動作、cache 生成への budget / slots / min-token 転送。
- `engine/include/strata/core/conversation_memory.hpp:128-139` — 自動容量の算出式、上限、刻み、無効条件。
- `engine/include/strata/core/conversation_cache.hpp:302-315,633-641` — 有効条件と RAM budget 内での保存。
- `engine/src/program/generate.cpp:14380-14387,14484-14516` — RAM 下限確認、保存拒否、park 結果および割り当て失敗時のログと継続。
- `engine/src/program/generate.cpp:11095-11104` — `--serve` が要求を stdin から受け付ける実行モード。
