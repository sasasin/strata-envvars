# `--mtp-q4`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。`generate` の引数解析） |
| オプション | `--mtp-q4` |
| 別名 | なし |
| 値 | `all`、`proj`、`head` のいずれか |

## 役割

MTP（multi-token prediction）draft layer の重みの一部をロード時に Q4_0 へ量子化したコピーに置き換え、draft step あたりの読み込み量を減らす opt-in オプションです。`proj` は Q8_0 の dense projection 群、`head` は draft head、`all` は両方を対象にします。これは通常の生成モデル全体の量子化指定ではありません（`sycl/src/program/generate.cpp:759-760, 2046-2051`、`sycl/src/core/mtp.cpp:236-261, 270-298`）。

## 使い方

```sh
# MTP draft の projection 重みを Q4_0 コピーで実行
strata --mtp /path/to/mtp --spec 4 --mtp-q4 proj

# projection と draft head の両方を対象にする
strata --mtp /path/to/mtp --spec 4 --mtp-q4 all
```

`--mtp` と `--spec` は例示です。MTP が有効でない実行では、この設定を適用するロード経路に入りません（`sycl/src/program/generate.cpp:4442-4450`）。

## 値と既定値

| 値 | 対象 |
| --- | --- |
| `proj` | `dense.bin` 内の Q8_0 tensor のうち、列数が 32 の倍数である projection。ロード時に float へ戻して Q4_0 に再量子化します。 |
| `head` | MTP draft head の語彙部分集合の各行。元 head の形式から float を経て Q4_0 にします。 |
| `all` | 上記の両方。 |

省略時は空文字列で、両方とも無効です（`sycl/src/program/generate.cpp:759-760`）。値は必須で、上記以外は標準エラーに `strata generate: --mtp-q4 takes all, proj or head` を出して parser が終了コード 2 を返します（同 `generate.cpp:2046-2051`）。値の重複指定について専用の拒否処理はなく、parser は各指定を読み、最後に保存された値を利用します。値を省いた場合の診断は `next()` の共通実装に委ねられます。

## 実行時の動作

MTP のロード前に `set_q4` を呼びます。`all` は projection と head の両フラグ、`proj` / `head` は該当側だけを有効にします（`sycl/src/program/generate.cpp:4442-4450`、`sycl/include/strata/core/mtp.hpp:64-67`）。projection 側では `dense.bin` の Q8_0 tensor を走査して Q4_0 コピーを作り、デバイスメモリを追加確保してコピーします。行列演算側は `wq()` を通じて Q4_0 コピーが存在する重みを選び、なければ元の Q8_0 を使います（`sycl/src/core/mtp.cpp:236-267, 903-908, 1024-1027`）。head 側は draft head 部分集合を変換して Q4_0 として扱います（同 `mtp.cpp:270-298, 865`）。

MTP は `--mtp` が空でなく、`--spec >= 2` のときにロードされます。`--mtp` を指定しても `--spec < 2` なら警告を出して MTP 指定をクリアするため、`--mtp-q4` の変換も起きません（`sycl/src/program/generate.cpp:4442-4449`）。このオプション自体には別の補正・fallback は見当たりません。

## 適用条件と副作用

- projection/head の変換は `STRATA_MTP_Q4` が有効なビルドでのみ実装されます。無効なビルドではロード失敗となり、「`--mtp-q4 needs a build with native experts (ggml)`」が返ります（`sycl/src/core/mtp.cpp:237-267, 270-302`）。
- `head` は埋め込み幅が 32 の倍数である必要があります。また Q6_K head が planar 配置（`STRATA_Q6_PLANAR`）なら、誤った draft head を無言で作るのを避けるため拒否します。その場合のエラーは packed Q6_K head layout（`STRATA_Q6_PLANAR=0`）を要求します（`sycl/src/core/mtp.cpp:273-281`）。
- 変換用ホストメモリと追加デバイスメモリを使います。projection コピーがデバイスに収まらない場合は失敗し、head の読出し・書込み、元形式の変換不可も個別の失敗経路があります（`sycl/src/core/mtp.cpp:246-260, 283-298`）。ロード失敗時、呼び出し側は診断と VRAM 空き容量の補足を stderr に出して終了コード 1 を返します（`sycl/src/program/generate.cpp:4459`）。
- 成功時は変換対象とサイズを stderr に表示します（`sycl/src/core/mtp.cpp:261, 296-297`）。量子化による出力品質・速度への影響はこの実装調査では評価していません。

## 根拠

- `sycl/src/program/generate.cpp:759-760` — オプションの既定状態と値の意味。
- `sycl/src/program/generate.cpp:896-897, 2046-2051` — help 表示、parser の受理値と不正値エラー。
- `sycl/src/program/generate.cpp:4442-4450, 4459` — MTP の適用条件、ロード前設定、ロード失敗時の終了経路。
- `sycl/src/core/mtp.cpp:236-267, 270-302` — projection/head の変換、メモリ確保、形式制約とエラー。
- `sycl/src/core/mtp.cpp:903-908, 1024-1027` — draft 層の実行時に対象 projection 重みを選ぶ箇所。
- `sycl/include/strata/core/mtp.hpp:64-67` — MTP drafter への設定 API。
