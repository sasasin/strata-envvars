# `--vram-reserve-later-mib`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ engine。`src/program/generate.cpp` の引数 parser） |
| オプション | `--vram-reserve-later-mib` |
| 別名 | なし |
| 値 | 整数 MiB。parser は `std::atoi` で変換する |

## 役割

`--layer-split` でモデルを複数GPUへ層分割したとき、先頭以外の GPU に残す VRAM の基準量を MiB で指定します。ディスプレイを接続していない後段 GPU の余裕を先頭 GPU と別に調整する用途です。ソースコメントは「後段カードの reserve は省略時に先頭と同じ」と説明しています（`src/program/generate.cpp:617-619`）。

## 使い方

```sh
strata --serve --pack /path/to/pack --native /path/to/model.gguf \
  --layer-split 24 --vram-reserve-mib 300 --vram-reserve-later-mib 1800
```

この例では、先頭 GPU の予約基準を 300 MiB、後段 GPU の予約基準を 1800 MiB にします。複数の境界で3台以上へ分割する場合も、オプションは一つで、全ての後段 stage に共通して使われます。`--layer-split` は `--serve` を必要とし、`24` のような値は後段 GPU が担当する最初の層番号です（`src/program/generate.cpp:2998-3027`）。

## 値と既定値

- 値は必須です。次の argv 要素がなければ stderr に `<option> needs a value` を出して終了コード 2 で終了します（`src/program/generate.cpp:2418-2420,2572-2573`）。
- 文字列を `std::atoi` で `int` に変換します。専用の範囲・形式 validation はありません。そのため数値として読めない値は `atoi` の規則で 0 になり、数値の後ろにある非数値部分も検査されません（`src/program/generate.cpp:2572-2573`）。
- 未指定時の内部値は `-1` です。後段予約の選択時に `-1` を sentinel として扱い、その実行時点の `--vram-reserve-mib` の値を使います。`--vram-reserve-mib` 自体の初期値は 700 MiB ですが、他の起動時調整があるため、常に 700 になるとは限りません（`src/program/generate.cpp:611-619,4566-4570`）。
- 0 以上の値は後段の予約基準として採用されます。負数はエラーにならず、既定と同様に `--vram-reserve-mib` へ戻ります。複数回指定した場合は parser が順に代入し、最後に読んだ値が残ります（`src/program/generate.cpp:2416-2421,2572-2573,4567-4569`）。

## 実行時の動作

後段 GPU の空き容量から、指定された予約基準に加えて、prefill 用領域、window、pipeline window、条件に応じた drafter 用領域を差し引き、expert cache に使える容量を計算します。`--layer-split auto` の候補容量計算と、分割確定後の後段 cache 容量計算の双方でこの値を参照します（`src/program/generate.cpp:4560-4571,4573-4585,6538-6556`）。

この値は VRAM を直接確保・固定する指定ではありません。後段 GPU に残す空き容量を見積もって expert cache の容量や自動分割の判断に反映し、後段 GPU の起動後メモリ診断にも使います。別途必要な window 等の容量は予約基準に加算されます（`src/program/generate.cpp:4566-4571,11032-11055`）。

後段 GPU ごとの起動後空き容量が 512 MiB 未満なら stderr に `LOW` 警告を出し、指定値から算出した参考値とともに `--vram-reserve-later-mib` の追加、または `--max-context` の引き下げを案内します。512 MiB 以上なら GPU 番号と空き容量を stderr に記録します。`cudaMemGetInfo` が失敗した場合、その GPU のこの診断はスキップされます（`src/program/generate.cpp:11032-11055`）。

## 適用条件と副作用

- 後段 GPU を持つ layer split の容量計算が主な適用先です。layer split がなければ、後段 stage の room 計算・診断は行われません（`src/program/generate.cpp:2998-3030,6538-6544,11032-11041`）。
- `--layer-split auto` では候補配置の容量・cache 見積もりを変え、選ばれる分割位置や各 GPU の cache 容量に影響し得ます。手動分割でも後段 GPU の expert cache に割り当て可能と見積もる容量に反映します（`src/program/generate.cpp:4573-4585,4680-4704,6538-6556`）。
- 予約を小さくすると計算上 cache に回せる容量が増えますが、window の初回 graph capture など後から必要になる空き容量を圧迫する可能性があります。ソースは 512 MiB 未満で後段 GPU の window graph に必要な余裕が少ないとして警告します（`src/program/generate.cpp:11001-11010,11032-11055`）。実際の性能改善や安全な推奨値はこのコードからは断定できません。
- `--vram-reserve-mib` とは別の値を設定でき、指定しなければそちらの値が使われます。複数の後段 GPU を使う構成でも、後段 GPU ごとの個別指定はありません（`src/program/generate.cpp:4567-4569,11036-11055`）。
- `--native` で Qwen3.6 (`qwen35moe`) を選ぶと、通常 parser より前に専用実装へ委譲されます。その専用 parser は `--serve` を処理済みで serve mode に入っている場合（通常は `--serve` を先に指定した場合）、未対応 option を値とともに無視して警告し、serve mode でなければ usage を出して終了コード 2 にします。このファミリーでは本オプションは後段 GPU 予約を制御しません（`src/program/generate.cpp:2394-2406`; `src/qwen35/q36_engine.cu:3742-3748,3782-3795`）。

## 出力とエラー

- 値が欠けた場合: stderr に `--vram-reserve-later-mib needs a value`、終了コード 2（`src/program/generate.cpp:2418-2420,2572-2573`）。
- 未知 option の一般経路: stderr に `unknown argument: ...` と usage を出し、終了コード 2。ただし上記 Qwen3.6 の serve 委譲経路では未対応 option は警告付きで無視されます（`src/program/generate.cpp:2787-2792`; `src/qwen35/q36_engine.cu:3782-3789`）。
- 後段 GPU の空き VRAM が 512 MiB 未満の場合の警告は上記「実行時の動作」を参照してください（`src/program/generate.cpp:11036-11055`）。

## 根拠

- parser と値変換: `src/program/generate.cpp:2416-2421,2571-2573`
- option の既定値と説明: `src/program/generate.cpp:611-619`
- 予約量を差し引く容量計算、自動分割: `src/program/generate.cpp:4560-4585,4680-4704`
- 手動・確定後 split stage の cache 容量見積もり: `src/program/generate.cpp:6538-6556`
- 後段 GPU の VRAM 診断: `src/program/generate.cpp:11032-11055`
- Qwen3.6 専用 parser への委譲と未対応 option の扱い: `src/program/generate.cpp:2394-2406`; `src/qwen35/q36_engine.cu:3735-3795`
- 利用者向け説明（ソース実装の補助資料）: `docs/MULTI_GPU.md:256-258`

調査範囲はこの checkout のソースと同 revision の索引・CLI 文書です。CLI バイナリの `--help`、Release 配布物、各 GPU/backend での実行結果は確認していません。
