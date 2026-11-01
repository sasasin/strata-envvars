# `STRATA_KVA_SUFFIX`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。外部ライブラリの環境変数は対象外です。

## 役割

KVA（approximate late-layer state）が適用される prompt の末尾に残す、完全計算位置数を指定します。既定値は 2048 です。値が正ならその数を使い、未設定・空文字・0・負数・整数として読めない文字列は 2048 に戻ります。これは `STRATA_KVA` 自体を有効にするスイッチではありません。KVA が無効または適用条件を満たさない prompt では、この値による近似範囲の変更はありません。

## 値と判定

共通 helper は `std::getenv()` で値を得て、未設定または空文字なら helper に渡された既定値を返し、それ以外は `std::atoll()` で `int64_t` に変換します。Suffix の呼び出し側は変換値を `max(0, value)` で下限 0 にし、`effective_suffix()` は正値だけを採用します。従って、有効な tail は最低でも既定値の 2048 です。

| 環境値 | 読み取り後の `suffix_env` | 実際の tail |
|---|---:|---:|
| 未設定、空文字 | 0 | 2048 |
| `0`、負数 | 0（負数は 0 に clamp） | 2048 |
| 正の整数（例: `3000`） | その整数 | その整数 |
| 数字で始まらない文字列（例: `abc`） | `atoll` の変換結果 0 | 2048 |
| 数字の後ろに文字が続く値（例: `3000tail`） | 先頭の整数 3000 | 3000 |

`atoll` のため、先頭の空白や符号は整数変換に従います。Strata 側は文字列全体の妥当性や範囲を別途検査せず、エラーを返しません。int64 の範囲外入力に対する結果はこのコードで定義・処理されていません。

## 有効になる条件

Suffix が実際に近似範囲を決めるには、KVA が有効である必要があります。KVA の設定は `STRATA_KVA` が空でなく先頭文字が `0` 以外であることを要求し、さらに次の制約があります。

- CUDA/HIP の state-only late-layer path があるビルドであること。Metal は `kKvaBackend` が false になり、適用されません。SYCL engine にも KVA prompt path はありません。
- 通常は測定済み形状の 48 layers / 512 experts であること。異なる形状は既定で除外され、`STRATA_KVA_ANY_MODEL` を有効にした場合のみ警告付きで許可されます。
- 単一 GPU で、`--batch` の batch slots、`--peer-device`、GPU 間 layer split を使わないこと。
- cold read（`pos0 == 0`）、全 trunk の read、画像なし、DFlash2 prompt taps なしであること。
- prompt 長が `STRATA_KVA_MIN_PROMPT` 以上で、かつ `effective_suffix + 64` より大きいこと。既定の最小長は 4096 です。

上記の最小 prompt 長や split は別設定です。CLI の suffix 専用引数はこの実装・設定表にはなく、`STRATA_KVA_SUFFIX` は `STRATA_KVA` や他の条件を上書きしません。suffix が大きく prompt に近い場合、KVA の `decline()` が「suffix leaves too few positions to approximate」として prompt 全体を正確な経路に戻します。

## 実行時の詳細

実行時の設定は `kva_config()` の function-local `static const KvaConfig` に初回アクセス時に一度だけ作られます。したがって、通常の engine 実行ではプロセス起動後に環境値を変更しても反映されません。`kva_config_from_env()` 自体は都度読み直す helper ですが、本番の prompt 経路は cache された `kva_config()` を利用します。Suffix として独立した cache やリクエストごとの再読込はありません。

各 read で `frontier = max(0, n - effective_suffix)` を計算し、chunk の終端 `p0 + T` が frontier 以下の chunk だけを近似対象にします。suffix にかかった chunk は通常経路で全レイヤーを実行します。そのため chunk 境界により、要求された tail より前の一部も正確に処理されることがあります。suffix は近似位置数の上限を決める値であり、正確にその数だけを残す保証ではありません。KVA が適用される chunk では `STRATA_KVA_SPLIT` 以降の対象レイヤーが state-only 等の KVA 処理になります。

適用・不適用の可視結果は stderr の prefill ログです。適用時は `strata prefill: KVA on: ... suffix <数値> ...` に実効 suffix が表示されます。不適用時は `KVA configured but NOT applied: ...` に理由、prompt 長、suffix、split が出ます。Suffix の変換だけを理由に終了・エラーにする処理は見つかりません。suffix が大きすぎる場合は KVA を適用せず通常の正確な read に戻ります。

## 根拠

- `include/strata/prefill/kva.hpp:54-57,86,95-96` — 既定 tail 2048、suffix 設定フィールド、正値のみを使う `effective_suffix()`。
- `include/strata/prefill/kva.hpp:137-140,149-159,191-195` — env helper の未設定・空文字処理、`atoll` 変換、負値 clamp、設定全体の process-local cache。
- `include/strata/prefill/kva.hpp:104-133` — KVA の適用条件と `n <= effective_suffix() + 64` の decline 判定。
- `src/program/generate.cpp:6257-6278` — backend 非対応および batch / peer / multi-GPU 条件で KVA を止める engine 側処理と stderr ログ。
- `src/prefill/prefill.cpp:2947-2966,3115-3123` — 実効 suffix の取得、frontier 計算、chunk 境界での近似判定。
- `src/prefill/prefill.cpp:3619-3629,3382-3393` — split 以降の対象 layer 処理と、近似対象 layer の expert transfer を省く分岐。
- `src/prefill/prefill.cpp:5820-5856` — 適用時の suffix 表示、不適用理由の stderr ログ。
- `docs/KVA.md:10-14,43-63,106-128` — KVA が opt-in であること、suffix の説明と設定一覧、適用条件・ログ例。実装の既定値 2048 と一致します。
- `docs/envvars/000_envvers.md:984` — 調査候補一覧にもこの名前があります。
