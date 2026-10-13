# `STRATA_PEER_HOT_AT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。Strata 所有ソースを対象とし、外部ライブラリや GPU ドライバーが読む環境変数の動作は扱わない。

## 役割

`--peer-device` 用の expert profile 順位変更で、peer GPU 向けに振り分ける対象の先頭範囲を指定します。環境変数の値 `at` は profile の先頭から何件を候補にするかを表し、実際の候補数は profile 件数を上限にします。候補内のどの順位を peer 向けに回すかは `STRATA_PEER_HOT` の比率で決まり、この変数だけでは並べ替えは有効になりません。

## 値と判定

profile 読み込み後、`--peer-device` が有効なときに `std::getenv("STRATA_PEER_HOT_AT")` で読み、設定されていれば `std::atoll()`、未設定なら `8700` を使います。その結果を `size_t` に変換してから `profile.size()` と小さい方を採ります。文字列全体の検証はなく、10進整数として読める先頭部分が使われます。先頭の空白と符号は `atoll` の規則に従い、後続の非数字は読み取りを止めます。

| 環境変数の状態・値 | `at` と処理 |
|---|---|
| 未設定 | 既定値 8700。ただし `profile.size()` を超えない |
| 空文字、数値で始まらない文字列 | `atoll()` が 0 を返すため `at = 0`。順位変更なし |
| 正の整数 `N` | `min(profile.size(), N)` 件を候補範囲にする |
| 0 | `at = 0`。順位変更なし |
| 負の整数 | `size_t` への変換で大きな符号なし値になり、通常は profile 全件が候補範囲になる |
| 整数の後に文字が続く値（例: `2000abc`） | 数値部分を読むため 2000 件（profile 件数が少なければその件数） |

整数の表現範囲を超える文字列に対する `atoll()` の結果は C ライブラリの仕様上保証されないため、文書化できる有効値として扱えません。

並べ替えの実行には別変数 `STRATA_PEER_HOT` の値 `f` が `0 < f < 1` であることも必要です。未設定なら `f = 0.45`、設定されている場合は `atof()` の結果です。`f` が範囲外、または `at == 0` なら profile は変更されず、順位変更ログも出ません。比率の詳しい判定規則は [`STRATA_PEER_HOT.md`](STRATA_PEER_HOT.md) を参照してください。

## 有効になる条件

- `--peer-device` が 1 以上であること。無効時はこの環境変数の読み取りと順位変更を行いません。
- `--expert-profile` が指定され、profile の読み込みに成功すること。読み込み失敗時はエラー終了します。
- `at > 0` かつ `STRATA_PEER_HOT` の比率 `f` が厳密に `0 < f < 1` であること。
- peer tier を初期化するには expert source と CUDA0 の expert cache も必要です。`--peer-device` は `--layer-split` および `--expert-cache-device1..3` と併用できません。

SYCL 実装にも同じ profile 順位変更処理がありますが、SYCL の `PeerExperts::open()` は `--peer-device: the second-GPU expert tier is not ported to SYCL yet` を返します。このため SYCL では並べ替えが行われても peer tier 初期化は失敗し、環境変数による実用上の peer 配置には至りません。

## 実行時の詳細

値は起動時の profile 読み込み直後に評価されます。先頭 `at` 件を順位 `r`（0 始まり）で走査し、`int64((r + 1) * f) > int64(r * f)` を満たす組を `moved`、それ以外を `keep` に分けます。出力 profile は `keep`、元 profile の順位 `at` から `fill - 1`、`moved`、残りの順です。`fill = min(profile.size(), at + moved件数)` です。したがって、この変数は peer の slot 数や cache 容量を指定するものではなく、peer が優先的に見る候補の順位構成を動かします。

CUDA の `PeerExperts::open()` は、primary cache がすでに保持する組を飛ばし、変更後の ranked list を順に走査して、peer の予約分を除いた空き VRAM と `--peer-slots` の範囲で収まる組を採用します。よって候補順位が変わっても、primary cache の内容、peer の空き容量、slot 上限により、最終的に peer に載る組数・内容は変わります。候補が一つも選べない場合は `peer experts: no room or no expert left for the peer` で初期化に失敗します。

有効な順位変更では stderr に次の形式でログが出ます。値の未設定や無効値そのものに対する警告はありません。

```text
strata generate: STRATA_PEER_HOT %.2f: %zu of the first %zu ranked pairs moved behind rank %zu (the peer's)
```

値は起動時に一度読むため、実行中に環境変数を変更しても再評価されません。子プロセスへの転送処理はこの変数の参照箇所では確認できません。

## 根拠

- `STRATA_PEER_HOT_AT` の読み取り、既定値、profile 件数による上限、`STRATA_PEER_HOT` との有効条件、順位変更、stderr ログ: `src/program/generate.cpp:3490-3531`。
- 同じ処理を持つ SYCL 側: `sycl/src/program/generate.cpp:3361-3403`。
- peer device 指定と profile の CLI 引数: `src/program/generate.cpp:2099-2106`。
- `--peer-device` と `--layer-split` / remote cache の併用禁止: `src/program/generate.cpp:2607-2614`。
- profile 等が peer 初期化に必要な条件: `src/program/generate.cpp:5448-5465`。
- primary が持つ組を除外し、空き budget と slot 上限まで ranked list を選ぶ処理: `src/core/peer_experts.cpp:135-153`。
- SYCL peer tier が未実装である旨のエラー: `sycl/src/core/peer_experts.cpp:19-23`。
- `docs/SECOND_GPU.md:131-173` は peer tier の profile 順利用、必要引数や排他条件を説明していますが、`STRATA_PEER_HOT_AT` の既定値・変換・範囲指定は記載していません。
