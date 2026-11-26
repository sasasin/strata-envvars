# `STRATA_FS_SLOTS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

正数を指定すると Foresight swap space を作り、expert cache にない expert の GGUF blob を各レイヤー・各 GPU に割り当てた追加 VRAM slots へ非同期コピーします。ルータの実際の選択は変えず、該当 expert のコピーが完了しているときだけ、その slot のアドレスを通常の GPU group として計算に使います。コピー未完了、slot がない、または交換中の expert は従来どおり CPU 側の miss になります（`engine/src/core/expert_source.cpp:5583-5606`, `engine/include/strata/core/foresight_swap.hpp:2-14`）。

この制御は `engine/src/program/generate.cpp` から `foresight_swap_from_env` を呼ぶ生成・serve の CUDA runtime 経路にあります。未設定または正数でない値では swap space を作らず、look-ahead 予測を Foresight slots へ送る経路も有効になりません。ファイル tier 向けの look-ahead は別条件で動く場合があります（`engine/src/program/generate.cpp:10296-10303,14887-14899`, `engine/src/core/expert_source.cpp:7294-7298`）。`--batch` のパイプライン並行読込を止める判定にも参照されます（「有効になる条件」参照）。

## 値と判定

主制御部は `std::getenv` の結果を `std::atoi` で `int` に変換し、0 以下なら無効、正数なら有効とします。`atoi` は文字列全体の妥当性を検証しません。したがって、空文字・数字で始まらない文字列・`0anything` は 0、`3tail` は 3、先頭空白と符号は変換規則に従い、大小文字の概念はありません。`atoi` で表せない範囲の値の扱いはこのコードで定義されていません。設定の有無だけで有効にする判定ではありません（`engine/src/core/expert_source.cpp:7296-7298`）。

| 判定箇所 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| swap space 作成・router look-ahead (`atoi(v) > 0`) | 無効 | `1`, `4`, `3tail` | 空文字, `0`, `0anything`, `-1`, `true` |
| `STRATA_PIPED_CONCURRENT` の競合判定 (`atoi(v) != 0`) | 競合なし | `1`, `-1`, `3tail` | 空文字, `0`, `0anything`, `true` |
| `STRATA_EXPERT_NIBBLE` の競合判定（値が空でない場合に `atoi(v) > 0`） | 競合なし | `1`, `3tail` | 空文字, `0`, `-1`, `true` |

swap space は指定値を最大 64 slots に丸めます。1 slot は各レイヤーの expert blob 1 個分で、割当量はレイヤー配置と blob サイズに依存します（`engine/src/core/expert_source.cpp:7064-7080,7296-7313`）。

## 有効になる条件

- CUDA runtime の生成・serve 経路で初期化されます。`docs/DETAILS.md` はこの switch の適用先を CUDA と記載しています（`engine/src/program/generate.cpp:14887-14899`, `docs/DETAILS.md:1266`）。
- 起動時の device plan 検証で `STRATA_VERIFY_DEVICE_PLAN` または `STRATA_VERIFY_DEVICE_HITS` が設定され、かつ `atoi` が 0 以外なら swap space を作りません。stderr に `strata serve: foresight swap: off beside STRATA_VERIFY_DEVICE_PLAN/HITS (the device would plan resident layers without the host)` を出します。これらの値は空文字や `0` ならこの拒否条件になりません（`engine/src/core/expert_source.cpp:7299-7305`）。
- VRAM の確保、非同期 copy stream、各 slot の CUDA event 作成に成功する必要があります。確保または stream 作成の失敗では swap space を無効にし、理由と `- swap space off` を stderr に出します。後続 slot event の作成失敗も `cannot create the copy events` として同じ失敗経路になります（`engine/src/core/expert_source.cpp:7082-7109,7313-7316`）。
- 選択された expert の source blob が利用でき、source が pin 済みの領域を提供し、同レイヤーで再利用可能な slot があり、当該カードの copy budget を超えていない場合にだけコピーを予約します。これらの条件を満たさない miss は引き続き CPU 側で処理されます（`engine/src/core/expert_source.cpp:7229-7278`）。
- look-ahead 予測から slot を埋める経路は、expert source があること、`STRATA_FS_SLOTS` が正数、`STRATA_FS_AHEAD` が未設定または `atoi` 非ゼロ、`STRATA_LOOKAHEAD` が未設定または `atoi` 非ゼロであることが必要です。router 重みが所定の BF16 形式でない場合などは look-ahead を開始せず、stderr に理由を出します。`STRATA_FS_AHEAD=0` は予測投入を止めますが、通常の miss からの swap copy は別経路です（`engine/src/program/generate.cpp:10292-10338`）。
- `STRATA_PIPED_CONCURRENT` の条件判定が初期化されるとき、`STRATA_FS_SLOTS` の `atoi` 結果が 0 以外なら `--batch` の concurrent prompt read を止めます。`strata batch: STRATA_PIPED_CONCURRENT is off beside STRATA_FS_SLOTS` と出ます。この gate は `static const` で初回評価結果を保持します（`engine/src/program/generate.cpp:21024-21046`, `engine/include/strata/program/batch_read.hpp:30-53`）。
- `STRATA_EXPERT_NIBBLE` の 4-bit slots が有効な CUDA build では、この変数が正数なら相互排他として拒否理由に使われます（`engine/include/strata/core/expert_nibble.hpp:277-299`, `engine/src/program/generate.cpp:3405-3441`）。

## 実行時の詳細

`foresight_swap_from_env` は生成処理の setup で `STRATA_FS_SLOTS` を読みます。正数なら `STRATA_FS_BUDGET`（既定 32、下限 1）、`STRATA_FS_ADMIT`（既定 1、下限 1）、`STRATA_FS_DEPTH`（既定 4、下限 2）、`STRATA_FS_VERIFY`（既定 0）も同時に読みます。slots 数だけは上限 64、他の3つは指定整数を下限へ clamp します。明示的な空文字や数値でない文字列は `atoi` により 0 となり、各設定の既定値または下限値になります（`engine/src/core/expert_source.cpp:7294-7321`）。CLI option による slots 数の上書きはこの読取箇所にはありません。

各カードにレイヤーごとの slot 領域を確保し、copy 用スレッドを開始します。miss は `note_miss`、look-ahead の次レイヤー予測は `predict` を通り、適格な blob を queue に積みます。コピーはカードごとの stream で行われ、event が完了するまでは利用しません。完了した slot は `take` が device pointer を返し、GPU 側 plan の kind 0 として処理されます。slot の再利用は、最後に参照した window から `STRATA_FS_DEPTH` 個以上の window が完了してからです（`engine/src/core/expert_source.cpp:7134-7158,7161-7195,7229-7278`, `engine/src/program/generate.cpp:14896-14907,22410,23125`）。

`STRATA_FS_SLOTS` と `fs_ahead` は swap space / 生成セットアップ単位で評価され、その instance の実行中は再読込しません。concurrent-read gate は別途、その gate に初めて到達したときの値を `static const` に保持します（`engine/src/program/generate.cpp:10296-10303,21024-21046`）。

## ログと測定値

初期化成功時は stderr に slots 数、カード数、カード・window あたりのコピー予算、admit miss 数、再利用までの window 数を表示します。実行中に非同期 copy が失敗すると `strata serve: foresight swap: a copy failed - swap space off` を出し、その後の新しい copy 要求は抑止されます。生成の report 箇所では swap から使った expert 数、copy 数、look-ahead 由来数、未完了数、空き slot 不足数、budget 超過数などを出します（`engine/src/core/expert_source.cpp:7134-7158,7281-7321`, `engine/src/program/generate.cpp:23392`）。

`docs/DETAILS.md:1266` は小さい cache が測定した全機種で返却 slot より高くついたため既定では off と記載しています。同文書の履歴表は 4 slots・6 pairs の比較として、RTX 3060、Tesla P100、RTX 5070、2x RTX 3090 の測定比を掲載しています（`docs/DETAILS.md:1712-1718`）。これらは資料中の報告値であり、この調査で再測定した値ではありません。

## 根拠

- `engine/src/core/expert_source.cpp:7059-7113,7134-7195,7218-7278,7294-7321`
- `engine/src/program/generate.cpp:10292-10338,14887-14907,21024-21046,23392`
- `engine/src/core/expert_source.cpp:5583-5606`
- `engine/include/strata/core/foresight_swap.hpp:2-21`
- `engine/include/strata/program/batch_read.hpp:30-53`
- `engine/include/strata/core/expert_nibble.hpp:277-299`; `engine/src/program/generate.cpp:3405-3441`
- `docs/DETAILS.md:1266,1712-1718`
