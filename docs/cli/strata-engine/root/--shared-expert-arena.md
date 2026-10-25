# `--shared-expert-arena`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。調査開始時の作業ツリーは `## main...origin/main` で、変更表示はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの引数 parser） |
| オプション | `--shared-expert-arena` |
| 別名 | なし |
| 値 | arena backing に使うファイルパスを1つ指定 |

## 役割

Linux で resident expert arena の backing を匿名メモリではなく `MAP_SHARED` のファイルにし、複数の Strata プロセスが同じファイルをマップできるようにします。engine の help は `/dev/shm` のような tmpfs を案内し、通常の SSD 上には置かないよう記しています（`src/program/generate.cpp:1063-1065`）。共有ファイルには4 KiBの識別ヘッダーが付き、その後ろが arena 本体です（`src/core/pinned.cu:89-91,158-159,223-234`）。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" \
  --shared-expert-arena /dev/shm/strata-experts.arena
```

`--tokens` は事前トークン化済み入力です。例のパスは共有用ファイルとして新規作成または再利用され、モデルの expert arena とほぼ同じ大きさの領域を必要とします。engine の usage とオプション説明は `src/program/generate.cpp:806-810,1063-1065` にあります。

## 値と既定値

- parser は次の argv を文字列として受け取り、数値・パス形式・空文字を検証しません。省略時は空文字で、通常の arena backing を使います（`src/program/generate.cpp:536-538,2754-2756`）。
- 値を省略すると `--shared-expert-arena needs a value` を stderr に出して終了コード2になります（`src/program/generate.cpp:2418-2420`）。値に空文字 `""` を明示した場合も空文字として扱われ、共有ファイル backing は有効になりません。複数回指定時は parser の走査で最後の値が残ります（`src/program/generate.cpp:2416-2420,2755`）。
- 相対パスはプロセスの作業ディレクトリ基準です。パスはそのまま `open()` に渡されます（`src/core/pinned.cu:158-161`）。

## 実行時の動作

- オプション値が空でない場合、通常の resident arena 初期化から `ArenaExpertSource::open()` に渡され、`PinnedArena` が共有ファイルの予約を行います（`src/program/generate.cpp:5905-5913`, `src/core/expert_source.cpp:5867-5878`）。
- Linux ではファイルを `O_RDWR | O_CREAT | O_CLOEXEC`、mode `0600` で開きます。サイズ0のファイルは `ftruncate()` でヘッダーと arena 分のサイズにし、識別ヘッダーを書き込みます。既存ファイルは期待サイズ、magic/version、arena サイズ、pack hash が一致しないと拒否されます（`src/core/pinned.cu:149-219`）。
- pack hash は expert geometry、pack の `manifest.json` / `index.txt` / `native_experts.txt`、および `experts.bin` または参照 GGUF のサンプルを使って作られます（`src/core/expert_source.cpp:5389-5423`）。これは別 pack の backing を取り違えないための照合です。既存 arena の中身を読み込み済みキャッシュとして再利用する処理はなく、通常の arena load が expert データを書き込みます（`src/core/expert_source.cpp:5880-5925`）。
- マップは `PROT_READ | PROT_WRITE, MAP_SHARED` です。arena の読込が進むと backing ファイルにも反映され、別プロセスが同じファイルをマップできます。ファイルは arena 解放時に unlink されません（`src/core/pinned.cu:223-234,657-678`）。
- shared file 使用時は cgroup/空きRAM の事前警告・拒否判定をスキップします。ソースコメントは別 engine がすでに同じ arena を RAM に持つ可能性を理由として挙げています（`src/core/expert_source.cpp:5760-5789`）。
- `--mmap-experts` とは併用できません。両方を有効にすると stderr に理由を出して終了コード2です（`src/program/generate.cpp:3039-3043`）。`--resident-experts` も `--mmap-experts` を有効化するため、同じ併用拒否になります（`src/program/generate.cpp:2757-2760,3039-3043`）。
- shared arena を使うと pin-by-need 用のページ境界パディングは使わず、プロセス間で共通の packed layout になります（`src/core/expert_source.cpp:5805-5817`）。

## 適用条件と副作用

- 通常 parser の resident expert arena 経路が対象です。`--mmap-experts` 経路とは排他です（`src/program/generate.cpp:5707-5719,5905-5913,3039-3043`）。dense モデル等で resident expert arena の初期化に到達しない場合、この値が backing に使われることはありません。
- 実装は POSIX 側のファイル mmap です。Windows は明示的に未実装で、値が空でなければ arena 予約失敗になります（`src/core/pinned.cu:97-100`）。help も Linux 用としています（`src/program/generate.cpp:1063`）。
- 新規 backing は指定ディレクトリに作成され、必要容量まで伸長されます。ディレクトリ・権限・容量不足などで open、stat、truncate、header write、mmap に失敗すると、arena 予約エラーになります（`src/core/pinned.cu:158-192,223-228`）。共有 backing を通常の永続 SSD に置く運用は help が推奨していません（`src/program/generate.cpp:1063-1065`）。
- 既存のサイズ0以外のファイルは切り詰められません。サイズやヘッダー、pack hash が不一致なら失敗します（`src/core/pinned.cu:194-219`）。
- 同一ファイルを複数プロセスが使う場合も、読込自体は各プロセスで実施されます。ソース上、共有ファイルの作成・読込をプロセス間で排他するロック処理は確認できませんでした。異なる pack で同じファイルを同時に初回作成する場合の動作は保証できる根拠が見つからず、ここでは断定しません。

## 出力とエラー

- 予約失敗は `ArenaExpertSource: the arena could not be reserved (...)` に原因文字列を付け、呼び出し元が `strata generate: ...` を stderr に出して終了コード1にします（`src/core/expert_source.cpp:5872-5878`, `src/program/generate.cpp:5906-5913`）。ファイル読込の失敗や読込 byte 数の不足も同様にエラーで終了します（`src/core/expert_source.cpp:5911-5925`）。
- `--mmap-experts` との併用拒否は stderr・終了コード2です（`src/program/generate.cpp:3040-3043`）。値の欠落も stderr・終了コード2です（`src/program/generate.cpp:2418-2420`）。
- 予約後の arena 読込経路は stderr に `expert arena read ...` を出します（`src/core/expert_source.cpp:5911-5919`）。通常、option 専用の stdout 出力は確認できませんでした。

## 調査範囲

索引の `strata-engine` は `src/program/generate.cpp` の parser を対象にしています（`docs/cli/README.md:1128-1134`）。同一 revision の既存実行ファイルは使わず、help 文言は同 revision のソース内 usage を補助資料として parser と照合しました。ビルド、実行、GPU 試験は行っていません。shared file の複数プロセス同時起動時における書き込み競合の挙動は実行確認していません。

## 根拠

- parser、help、排他条件、arena 呼び出し: `src/program/generate.cpp:1063-1065,2416-2420,2753-2756,3039-3043,5905-5913`
- arena の値検証、pack fingerprint、RAM 判定、予約後の読込: `src/core/expert_source.cpp:5389-5423,5680-5695,5760-5793,5805-5817,5867-5878,5911-5925`
- Linux/Windows backing 実装、ファイル生成と header 照合、mmap と解放: `src/core/pinned.cu:89-100,149-234,657-678`
- 文書配置と `strata-engine` の scope: `docs/cli/README.md:1128-1134,1280`; 配置・調査基準: `docs/cli/001_investigation.md`
