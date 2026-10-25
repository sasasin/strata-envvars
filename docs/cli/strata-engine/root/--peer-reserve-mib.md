# `--peer-reserve-mib`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数） |
| オプション | `--peer-reserve-mib` |
| 別名 | なし |
| 値 | MiB 単位の整数。peer GPU 上で expert cache 用に残す量を指定 |

## 役割

`--peer-device` で有効にする peer GPU の expert cache が使うメモリ量を抑え、その GPU に空けておく VRAM の目標値を指定します。peer device を指定しない場合、この値は peer cache の作成経路で使われません。

## 使い方

```sh
strata --pack /path/to/model.pack --expert-profile /path/to/profile.bin \
  --expert-cache 4096 --peer-device 1 --peer-reserve-mib 1024
```

これは既存モデル・profile を使う場合の引数例です。`--peer-device` の利用には `--expert-profile` と正の `--expert-cache` が必要です。

## 値と既定値

- 省略時の値は `600` MiB です。
- parser は値を `std::atoi` で `int` に変換します。値の欠落時は `--peer-reserve-mib needs a value` を stderr に出して終了コード 2 で終了します。
- このオプション自体には数値範囲の validation がありません。peer cache の容量計算では `max(指定値, 128)` を使うため、128 以下の値（負数を含む）も実効値 128 MiB になります。数値として解釈できない文字列は `atoi` の結果が 0 となり、この同じ下限が適用されます。
- 同じオプションを複数回指定した場合は parser が後の値を `Options` に代入します。

## 実行時の動作

`--peer-device N` が 1 以上の場合、エンジンは peer tier を開く際に本値を `PeerExperts::open` に渡します。そこで peer GPU の空きメモリを取得し、指定値（最低 128 MiB）を差し引いた残りを expert cache の予算にします。rank 順に primary cache にない expert を選び、予算または `--peer-slots` の上限に達したところで選択を止めます。従って値を大きくすると peer tier の expert 数が減り、小さくしても 128 MiB より低い予約にはなりません。

この予約計算は expert cache 選択前に行われます。peer prefill が使う GPU バッファも後段で割り当てられ、割り当て不能の場合は「`--peer-reserve-mib` を上げるか `--peer-prefill-rows` を下げる」旨のエラーになります。peer GPU 上に最終的に指定量が必ず空く保証としてではなく、後続処理の余裕を cache 選択時に差し引く指定として扱ってください。

## 適用条件と副作用

- 実際に値が使われるのは `--peer-device` が 1 以上のときだけです。その場合、`--expert-profile` が空、expert source がない、または `--expert-cache <= 0` なら起動失敗となります。
- `--peer-device` は `--layer-split` または `--expert-cache-device1..3` と併用できません。該当する場合、stderr に競合オプションを示して終了コード 2 で終了します。
- peer device 番号が CUDA で可視なデバイス範囲外なら、peer 初期化でエラーになります。選択後に peer cache の空きがない場合（expert が残っていない場合を含む）も初期化に失敗します。
- 初期化では peer GPU に stream、event、host/device staging・scratch buffer を確保し、選んだ expert を cache に読み込みます。GPU メモリ確保や expert の読み込み・検証に失敗した場合は peer を閉じ、エンジンがエラーを stderr に出して終了コード 1 で終了します。
- peer cache の初期化成功時、stderr に peer GPU の expert 数、使用量、読み込み時間、および primary cache と合わせた常駐数が表示されます。prefill peer 初期化が成功した場合も stderr に peer GPU の prefill 状態と残り MiB が表示されます。

## 根拠

- `src/program/generate.cpp:570-579` — peer 関連 option の既定値。`src/program/generate.cpp:1009-1015` — help に掲載された意味と既定値。
- `src/program/generate.cpp:2416-2421` — 値欠落時の処理。`src/program/generate.cpp:2743-2747` — `atoi` による parser 代入。未知引数の失敗処理は `src/program/generate.cpp:2787-2792`。
- `src/program/generate.cpp:3371-3375` — peer device と layer split / remote cache の併用拒否。
- `src/program/generate.cpp:6750-6766` — peer 起動条件、オプション値の引き渡し、失敗時の stderr と終了コード、成功ログ。
- `src/core/peer_experts.cpp:124-145` — peer GPU 可視性確認。`src/core/peer_experts.cpp:191-212` — 予約量の 128 MiB 下限、空きメモリからの予算計算、選択上限、空きなしエラー。`src/core/peer_experts.cpp:213-241` — arena 準備、expert の読み込み・検証。
- `src/prefill/prefill.cpp:2191-2209` — prefill buffer 不足時のエラーと成功時の残量表示。

調査は指定 revision の parser と参照箇所に限定しました。CLI バイナリの `--help` は実行せず、ビルド、GPU 実行、性能測定、テスト、Strata ソース変更は行っていません。巨大な整数値の `atoi` 変換境界や、各 GPU/backend での実際の確保可能量は実行確認していません。
