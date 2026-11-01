# `STRATA_CKPT_VRAM_SLOTS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の Strata 作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

非同期 conversation checkpoint の GDN 状態について、直近の保存状態を保持する CUDA device VRAM slot の上限数を指定します。保存時に slot が使えた checkpoint は、その GDN 状態のコピーを RAM に加えて VRAM にも保持し、復元時に対応する slot が残っていれば GDN を device-to-device で戻します。値は通常の同期 checkpoint 経路では参照されず、`STRATA_CKPT_ASYNC` が有効な保存だけに関係します（`src/core/conversation_state.cpp:183-190,305-326,392-414`）。

## 値と判定

`std::getenv` の結果を `std::atoi` で整数化し、`std::max(0, std::min(16, ...))` で 0〜16 に制限します。環境変数が未設定なら 0 です。設定された空文字や数値として読めない文字列は `atoi` が 0 を返すため、slot 数は 0 になります。`atoi` の通常の prefix 変換により、先頭の空白や符号は受け付け、数値の後ろにある文字列は値に影響しません。負値は 0、16 を超える値は 16 になります。`atoi` の整数範囲外の入力についてはコードに独自の検査がなく、動作を規定できません（`src/core/conversation_state.cpp:188-190`）。

| 入力例 | slot 上限 |
|---|---:|
| 未設定、空文字、`abc`、`0`、`-3` | 0 |
| `  +3tail` | 3 |
| `16`、`99` | 16 |

## 有効になる条件

- CUDA の `STRATA_CKPT_ASYNC` 経路であること。`STRATA_CKPT_ASYNC` は unset では無効で、設定値の先頭文字が `1` の場合に有効です。HIP、`STRATA_HIP_GFX906`、Metal では同機能が無効を返すため、この slot 設定も使われません（`src/core/conversation_state.cpp:208-214`）。
- GDN 状態のサイズが 1 MiB 以上であること。サイズ未満では非同期保存分岐に入らず、通常の host checkpoint copy になります（`src/core/conversation_state.cpp:295-305,362-363`）。
- slot 数が 1 以上であること。0 の場合、VRAM slot を探さず非同期 staging buffer を使います（`src/core/conversation_state.cpp:322-326`）。

この環境変数を上書きする CLI 引数や別設定は見つかりませんでした。`STRATA_CKPT_ASYNC` が無効なら、slot 数が正でも影響しません。

## 実行時の詳細

環境変数は `vram_slots_n()` の関数内 static 初期化で一度読み、整数値をプロセス内にキャッシュします。最初の評価後にプロセス環境を変更しても再評価されません（`src/core/conversation_state.cpp:188-190`）。

非同期保存では、現在の CUDA device と GDN 状態サイズに一致する slot のうち、LRU のものを候補にします。slot の総数が上限未満なら新規 slot の確保を先に試みますが、確保するには `cudaMemGetInfo` が成功し、空き VRAM が「状態サイズ + 1.5 GiB」より厳密に大きい必要があります。条件を満たさない、または `cudaMalloc` が失敗した場合は、同じ device・サイズの既存 slot があればそれを再利用し、なければ共有 async staging buffer を使います。したがって N は確保を保証する数ではなく、slot vector の最大件数です。状態サイズの異なる checkpoint 同士で slot は共有されません（`src/core/conversation_state.cpp:192-206,309-326`）。

slot への D2D copy に成功すると checkpoint に tag を付け、slot の LRU 時刻を更新してから、非同期処理で GDN bytes を host 側の checkpoint vector にも転送します（`src/core/conversation_state.cpp:326-360`）。復元時は tag、現在の device、サイズが一致する slot を検索し、hit ならその VRAM buffer から GDN をコピーします。hit しない場合は該当 checkpoint の非同期 host copy を join し、checkpoint vector の RAM bytes から復元します。その他の checkpoint 状態も RAM 側から復元します（`src/core/conversation_state.cpp:392-428`）。

slot の確保失敗や「空き VRAM が閾値以下」の場合に、この変数専用の警告は出ません。保存・復元 copy の失敗は `conversation snapshot ...` の error に入り、生成経路では `strata serve: checkpoint save: ...` または `strata serve: checkpoint restore: ...` と stderr に出ます。復元に失敗した場合、会話再開経路は stdout に `ERR restoring a conversation checkpoint failed` を出して終了コード 1 で戻ります（`src/core/conversation_state.cpp:27-45,272-278`; `src/program/generate.cpp:1915-1937,14680-14689`）。slot でなく async staging への保存へ fallback したり、host bytes から復元する場合は、この環境変数固有のログはありません。

## 根拠

- 実際の環境読み取り、変換、clamp、cache: `src/core/conversation_state.cpp:188-190`。
- Slot 選択、device/サイズ一致、空き VRAM 条件、LRU 候補: `src/core/conversation_state.cpp:192-206`。
- Async の backend 条件と GDN サイズ条件: `src/core/conversation_state.cpp:208-214,295-305`。
- 保存時の slot 利用、tag 付与、RAM への非同期 copy: `src/core/conversation_state.cpp:322-360`。
- 復元時の VRAM hit と RAM fallback: `src/core/conversation_state.cpp:392-428`。
- 呼び出し側のエラー表示・終了経路: `src/program/generate.cpp:1915-1937,14680-14689`。
- `docs/DETAILS.md:1504-1514` は CUDA の opt-in 機能として `STRATA_CKPT_ASYNC=1` との併用、slot 数 0〜16、空き VRAM 1.5 GB 条件を記載しています。記載値「N × 118 MB」と restore 時間は、同資料にある CMP 170HX（GA100, sm_80）/ PCIe Gen2 x4 での変更作者の測定であり、一般的な状態サイズや性能保証ではありません。実装上の slot サイズは各 checkpoint の `c.gdn.size()` で決まります。
